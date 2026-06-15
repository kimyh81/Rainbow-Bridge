import app.core.ai_path  # noqa: F401  # ai.* import 경로 등록(반드시 ai import 앞)

from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ai.evaluation.health_adapter import from_health_connect

from app.core.deps import get_current_user
from app.db.mongodb import mongodb

router = APIRouter()


class HealthSyncIn(BaseModel):
    pet_id: str
    steps_result: Optional[dict[str, Any]] = None
    sleep_result: Optional[dict[str, Any]] = None


@router.post("/sync", status_code=201)
async def sync_health(body: HealthSyncIn, user: dict = Depends(get_current_user)):
    """삼성헬스(→Health Connect) raw JSON 수신 → 어댑터로 {steps, sleep_hours} 파싱 →
    ``health_logs`` 에 날짜별 1건 upsert. 이후 ``GET /report`` 가 이 값을 읽어 회복점수에 반영.

    ⚠️ 수면은 회복점수서 제외(결정문서 §2) — ``sleep_hours`` 는 교차검증·표시로만,
    활동(``steps``)만 점수 반영(ai/evaluation 점수 로직에 이미 반영됨).
    """
    parsed = from_health_connect(
        body.steps_result, body.sleep_result
    )  # {steps, sleep_hours}
    today = datetime.now(timezone.utc).date().isoformat()
    await mongodb.db["health_logs"].update_one(
        {"pet_id": body.pet_id, "date": today},
        {"$set": {**parsed, "synced_at": datetime.now(timezone.utc)}},
        upsert=True,
    )
    return {"ok": True, "date": today, **parsed}
