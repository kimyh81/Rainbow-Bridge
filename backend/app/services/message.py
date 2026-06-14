import asyncio
import logging
import app.core.ai_path  # noqa: F401
from datetime import datetime, timezone

from bson import ObjectId

from ai.evaluation.logs import (
    COLLECTION as LLM_LOGS,
    KIND_CRISIS,
    KIND_MESSAGE,
    alog_llm_call,
    measure_latency,
)
from ai.llm.config import get_config
from ai.llm.memorial import GuardrailViolation, generate_message
from ai.llm.provider import generate
from ai.llm.safety import CRISIS_NOTICE, assess_crisis, CrisisAction, decide_action

from app.db.mongodb import mongodb
from app.db.redis_client import get_recent_emotions
from app.schemas.message import MessageCreate, MessageResponse
from app.services.emotion import get_recovery

logger = logging.getLogger(__name__)

CRISIS_HOTLINE = "1393"

_FALLBACK = {
    "warm": "함께한 시간들이 당신 마음 깊은 곳에서 언제나 따뜻하게 빛나고 있을 거예요. 그 소중한 기억들이 당신 곁에 늘 있습니다.",
    "calm": "소중한 인연은 시간이 지나도 마음속에 조용히 머뭅니다. 함께한 모든 순간이 당신의 일부로 남아 있어요.",
    "hopeful": "사랑했던 기억은 사라지지 않아요. 그 기억이 당신이 다시 일어설 수 있는 힘이 되어줄 거예요.",
}

_VALID_TONES = {"warm", "calm", "hopeful"}


def _collection():
    return mongodb.db["messages"]


async def _prefetch_tts(pet_id: str, content: str, pet: dict) -> None:
    """메시지 생성 직후 narration TTS를 백그라운드 미리 생성 (fire-and-forget)."""
    try:
        from app.schemas.tts import TtsCreate
        from app.services.tts import generate_tts

        species = pet.get("species", "강아지") or "강아지"
        await generate_tts(
            TtsCreate(text=content, tone="narration", pet_id=pet_id, species=species)
        )
        logger.info("TTS 미리 생성 완료 pet_id=%s", pet_id)
    except Exception:
        logger.warning("TTS 미리 생성 실패 pet_id=%s", pet_id, exc_info=True)


def _calc_recovery_trend(records: list[dict]) -> str | None:
    if len(records) < 3:
        return None
    scores = [r["score"] for r in records]
    mid = max(1, len(scores) // 2)
    recent_avg = sum(scores[:mid]) / mid
    older_avg = sum(scores[mid:]) / max(len(scores[mid:]), 1)
    if recent_avg > older_avg + 0.5:
        return "회복 중"
    if recent_avg < older_avg - 0.5:
        return "주의 필요"
    return None


async def get_latest_message(pet_id: str) -> MessageResponse | None:
    doc = await _collection().find_one(
        {"pet_id": pet_id, "source": {"$ne": "safety"}},
        sort=[("created_at", -1)],
    )
    if not doc:
        return None
    doc["id"] = str(doc.pop("_id"))
    return MessageResponse(**doc)


async def create_message(data: MessageCreate) -> MessageResponse:
    pet_doc = await mongodb.db["pets"].find_one({"_id": ObjectId(data.pet_id)})
    pet = dict(pet_doc or {})

    recovery_trend = None
    try:
        records = await get_recent_emotions(data.pet_id)
        recovery_trend = _calc_recovery_trend(records)
    except Exception:
        pass

    # 회복 게이트 — 1인칭 편지는 요청(보호자 동의) + 게이트 통과(창 내 risk=0) 동시 충족 시에만.
    # 조회 실패 시 fail-closed(잠금 유지).
    content_unlocked = False
    allow_first_person = False
    try:
        recovery = await get_recovery(data.pet_id)
        content_unlocked = recovery.content_unlocked
        allow_first_person = recovery.allow_first_person
    except Exception:
        pass
    first_person = data.request_first_person and allow_first_person

    tone = data.tone if data.tone in _VALID_TONES else "warm"
    note = data.note or ""
    emotion = {"emotion_score": data.emotion_score or 5, "note": note}

    # ⑧ 리포트용 라이트 로깅 메타 — 분기에서 채우고 finally 에서 1건 적재.
    cfg = get_config()
    log_kind, log_ok, log_risk = KIND_MESSAGE, True, None
    timer = None
    response: MessageResponse
    try:
        with measure_latency() as timer:
            # L0+L1 위기 선체크 — generate 주입으로 LLM 레이어(L1) 활성화
            crisis = assess_crisis(note, generate=generate)
            action = decide_action(crisis.risk_level)
            if action == CrisisAction.BLOCK:
                log_kind, log_risk = KIND_CRISIS, int(crisis.risk_level)
                doc = {
                    "pet_id": data.pet_id,
                    "content": CRISIS_NOTICE,
                    "tone": tone,
                    "source": "safety",
                    "risk_level": int(crisis.risk_level),
                    "created_at": datetime.now(timezone.utc),
                }
                inserted = await _collection().insert_one(doc)
                doc["id"] = str(inserted.inserted_id)
                response = MessageResponse(**doc)
                response.crisis_message = CRISIS_NOTICE
            else:
                try:
                    result = generate_message(
                        pet=pet,
                        emotion=emotion,
                        tone=tone,
                        generate=generate,
                        source="local",
                        first_person=first_person,
                        recovery_trend=recovery_trend,
                    )
                except GuardrailViolation:
                    log_ok = False
                    result = {
                        "content": _FALLBACK[tone],
                        "tone": tone,
                        "source": "fallback",
                    }

                doc = {
                    "pet_id": data.pet_id,
                    "content": result["content"],
                    "tone": result.get("tone", tone),
                    "source": result.get("source", "local"),
                    "risk_level": result.get("risk_level", 0),
                    "created_at": datetime.now(timezone.utc),
                }
                inserted = await _collection().insert_one(doc)
                doc["id"] = str(inserted.inserted_id)

                # 위기(safety) 메시지는 타임라인에 포함하지 않음
                if result.get("source") != "safety":
                    await mongodb.db["pets"].update_one(
                        {"_id": ObjectId(data.pet_id)},
                        {
                            "$push": {
                                "timeline_refs": {
                                    "type": "message",
                                    "ref_id": doc["id"],
                                }
                            }
                        },
                    )

                response = MessageResponse(**doc)
                # 회복 게이트 상태 + 1인칭 실제 적용 여부를 프론트에 전달
                response.first_person = first_person
                # 1인칭 편지 생성 시 d3 입모양 영상 백그라운드 트리거 (voiced_url 준비)
                if first_person:
                    from app.services.media import trigger_liveportrait_for_pet

                    asyncio.create_task(trigger_liveportrait_for_pet(data.pet_id))
                # narration TTS 미리 백그라운드 생성 — 사용자가 재생 버튼 누를 때 이미 준비
                asyncio.create_task(_prefetch_tts(data.pet_id, result["content"], pet))
                response.content_unlocked = content_unlocked
                response.allow_first_person = allow_first_person
                if result.get("crisis_message"):
                    response.crisis_message = result["crisis_message"]
                if result.get("support_message"):
                    response.support_message = result["support_message"]
                if result.get("welfare_resources"):
                    response.welfare_resources = result["welfare_resources"]

    finally:
        # best-effort — 로그 적재 실패가 사용자 응답을 깨면 안 됨.
        try:
            await alog_llm_call(
                mongodb.db[LLM_LOGS],
                kind=log_kind,
                pet_id=data.pet_id,
                model=cfg.model,
                provider=cfg.provider,
                latency_ms=timer.ms if timer else 0,
                ok=log_ok,
                risk_level=log_risk,
            )
        except Exception:
            pass

    return response
