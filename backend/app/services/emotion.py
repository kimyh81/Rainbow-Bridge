from ai.evaluation.recovery_signal import recovery_score
from app.services.mission import get_completed_mission_count, get_mission_completed_days
from datetime import datetime, timezone
import app.core.ai_path  # noqa: F401  프로젝트 루트를 sys.path에 추가
from ai.llm.safety import assess_crisis
from ai.llm.provider import generate
from app.db.mongodb import mongodb
from app.db.redis_client import get_recent_emotions, push_emotion
from app.schemas.emotion import EmotionCreate, EmotionResponse, RecoveryResponse

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
    # 반소람님 assess_crisis() — L1 LLM 레이어 연동
    crisis = assess_crisis(data.note or "", generate=generate)
    risk_level = int(crisis.risk_level)
    doc = data.model_dump()
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

        # 회복 점수 — 감정40 / 미션누적35(sticky) / 꾸준함25
    completed_missions = await get_completed_mission_count(pet_id)
    completed_days = await get_mission_completed_days(pet_id, days=14)
    consistency_pct = round(completed_days / 14 * 100)
    recovery_pct = recovery_score(
        emotion_avg=avg,
        completed_missions=completed_missions,
        consistency_pct=consistency_pct,
    )

    # 창(window) 내 최대 risk — 직전 L3 위기가 있었으면 여전히 잠금 유지
    max_risk = max(r.get("risk_level", 0) for r in records)
    latest_risk = records[0].get("risk_level", 0)

    content_unlocked = (
        len(records) >= _GATE_MIN_CHECKINS
        and avg >= _GATE_MIN_AVG_SCORE
        and max_risk <= _GATE_MAX_RISK
        and trend != "주의 필요"
    )
    # 1인칭 편지는 창 내 위기 기록이 전혀 없을 때만 허용
    allow_first_person = content_unlocked and max_risk == 0

    # 3단계 게이트: locked(0~49) / teaser(50~79) / open(80+)
    if not content_unlocked:
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
        gate_status=gate_status,
    )
