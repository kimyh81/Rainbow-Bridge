from ai.evaluation.recovery_signal import recovery_score_from_axes
from datetime import date, datetime, timezone
import app.core.ai_path  # noqa: F401  프로젝트 루트를 sys.path에 추가
from bson import ObjectId
from ai.evaluation.pii import redact
from ai.llm.safety import assess_crisis
from ai.llm.provider import generate
from app.db.mongodb import mongodb
from app.db.redis_client import get_recent_emotions, push_emotion
from app.schemas.emotion import EmotionCreate, EmotionResponse, RecoveryResponse
from app.services.health_lifestyle import get_lifestyle_pct

CRISIS_HOTLINE = "1393"

# ── 회복 게이트 임계값 ──────────────────────────────────────────
# 미션 난이도 확정 후 조정하세요 (모세종 담당)
_GATE_MIN_CHECKINS = 3  # 최소 체크인 횟수
_GATE_MIN_AVG_SCORE = 5.0  # 평균 감정 점수 하한 (1~10)
_GATE_MAX_RISK = 1  # 허용 최대 risk_level (2 이상이면 잠금 유지)
# ────────────────────────────────────────────────────────────────


def _collection():
    return mongodb.db["emotions"]


async def create_emotion(data: EmotionCreate) -> EmotionResponse:
    # 비식별화 — note 원문을 LLM(Gemini) 전송·DB 저장 전에 PII 가림.
    # 반려동물 이름(pet 레코드)은 정확 치환, 전화·이메일은 best-effort.
    # 조회 실패해도 연락처 마스킹은 진행(graceful).
    try:
        pet_doc = await mongodb.db["pets"].find_one({"_id": ObjectId(data.pet_id)})
        pet_name = (pet_doc or {}).get("name") or ""
    except Exception:
        pet_name = ""
    safe_note = redact(data.note, pet_names=[pet_name] if pet_name else [])

    # 위기판정 — 규칙(L0)은 원문으로(미탐 0), LLM(L1)에만 가린 텍스트 전송(PII 비전송).
    # 융합이 max 라 가림으로 신호가 약해져도 규칙 floor 아래로 안 내려감.
    crisis = assess_crisis(data.note or "", generate=generate, llm_text=safe_note)
    risk_level = int(crisis.risk_level)
    doc = data.model_dump()
    doc["note"] = safe_note  # 원문 PII 미저장 — 가린 note 만 적재
    doc["risk_level"] = risk_level
    doc["created_at"] = datetime.now(timezone.utc)
    result = await _collection().insert_one(doc)
    doc["id"] = str(result.inserted_id)

    # Redis에 최근 감정 기록 캐시 (회복 분석용)
    try:
        await push_emotion(
            pet_id=data.pet_id,
            score=data.score,
            risk_level=risk_level,
            created_at=doc["created_at"].isoformat(),
        )
    except Exception:
        pass  # Redis 장애가 체크인 자체를 막지 않도록

    response = EmotionResponse(**doc)
    if crisis.hotline_required:
        response.crisis_message = (
            f"많이 힘드시군요. 혼자 감당하기 어려울 때는 "
            f"자살예방상담전화 {CRISIS_HOTLINE}로 연락해 주세요. 24시간 운영합니다."
        )
    return response


async def get_recovery(pet_id: str) -> RecoveryResponse:
    records = await get_recent_emotions(pet_id)

    if not records:
        return RecoveryResponse(
            pet_id=pet_id,
            total_checkins=0,
            avg_score=None,
            trend="데이터 없음",
            recovery_pct=0,
            latest_risk_level=None,
            records=[],
        )

    scores = [r.get("score", 0) for r in records]
    avg = round(sum(scores) / len(scores), 1)

    # 회복 추이: 최근 절반 vs 앞쪽 절반 점수 비교
    mid = max(1, len(scores) // 2)
    recent_avg = sum(scores[:mid]) / mid
    older_avg = sum(scores[mid:]) / max(len(scores[mid:]), 1)
    if recent_avg > older_avg + 0.5:
        trend = "회복 중"
    elif recent_avg < older_avg - 0.5:
        trend = "주의 필요"
    else:
        trend = "유지 중"

    # 회복 점수 — 4축(미션40·지속성30·감정추세15·생활패턴15) 일원화
    mission_col = mongodb.db["missions"]
    missions_list = []
    async for m in mission_col.find({"pet_id": pet_id}):
        created = m.get("created_at")
        date_str = (
            created.date().isoformat()
            if hasattr(created, "date")
            else str(created)[:10]
        )
        missions_list.append(
            {
                "date": date_str,
                "done": bool(m.get("completed", False)),
                "difficulty": m.get("difficulty", ""),
            }
        )
    # 생활패턴(15%) — 걸음(40%)+수면(30%)+야간 폰사용(30%) 합성. 없으면 무페널티 제외.
    lifestyle_pct = await get_lifestyle_pct(pet_id)

    # 창(window) 내 최대 risk — 직전 L3 위기가 있었으면 여전히 잠금 유지
    max_risk = max(r.get("risk_level", 0) for r in records)
    latest_risk = records[0].get("risk_level", 0)

    # L2~3(max_risk>=2)이면 회복점수를 41로 cap — content_unlocked(max_risk 기준)와
    # 같은 기준으로 점수·게이트가 어긋나지 않게 한다(RECOVERY_SCORE_DESIGN.md §6).
    recovery_pct = recovery_score_from_axes(
        missions_list,
        records,
        lifestyle_pct=lifestyle_pct,
        as_of=date.today(),
        risk_level=max_risk,
    )

    content_unlocked = (
        len(records) >= _GATE_MIN_CHECKINS
        and avg >= _GATE_MIN_AVG_SCORE
        and max_risk <= _GATE_MAX_RISK
        and trend != "주의 필요"
    )
    # 1인칭 편지는 창 내 위기 기록이 전혀 없을 때만 허용
    allow_first_person = content_unlocked and max_risk == 0

    gif_unlocked = recovery_pct >= 20

    # 3단계 게이트: locked(0~44) / teaser(45~79) / open(80+)
    if not content_unlocked or recovery_pct < 45:
        gate_status = "locked"
    elif recovery_pct >= 80:
        gate_status = "open"
    else:
        gate_status = "teaser"

    return RecoveryResponse(
        pet_id=pet_id,
        total_checkins=len(records),
        avg_score=avg,
        trend=trend,
        recovery_pct=recovery_pct,
        latest_risk_level=latest_risk,
        records=records,
        content_unlocked=content_unlocked,
        allow_first_person=allow_first_person,
        gif_unlocked=gif_unlocked,
        gate_status=gate_status,
    )
