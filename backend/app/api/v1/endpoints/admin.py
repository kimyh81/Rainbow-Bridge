"""어드민 엔드포인트 — LLM 사용 현황 집계."""

import json
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException

from app.core.config import settings
from app.db.mongodb import mongodb
from app.db.redis_client import get_redis

router = APIRouter()


@router.get("/usage", tags=["admin"])
async def get_usage():
    """llm_logs 컬렉션 기반 LLM 호출 현황을 반환합니다.

    llm_logs 도큐먼트 예시 (ai/evaluation/logs.py LLMLog 와 정합):
        {"kind": "message", "provider": "gemini", "model": "gemini-2.5-flash",
         "total_tokens": 512, "latency_ms": 420, "ok": true}
    ⚠️ 대화 원문(prompt/응답 텍스트)은 저장하지 않습니다(개인정보 최소화).
    """
    collection = mongodb.db["llm_logs"]

    # 전체 호출 수
    total_calls = await collection.count_documents({})

    # 모델별 집계 (호출 수 + 토큰 합계)
    pipeline = [
        {
            "$group": {
                "_id": "$model",
                "calls": {"$sum": 1},
                "tokens": {"$sum": "$total_tokens"},
            }
        }
    ]
    by_model = {}
    total_tokens = 0
    async for doc in collection.aggregate(pipeline):
        model_name = doc["_id"] or "unknown"
        by_model[model_name] = {"calls": doc["calls"], "tokens": doc["tokens"]}
        total_tokens += doc["tokens"]

    # 최근 20개 로그
    cursor = collection.find(
        {},
        sort=[("_id", -1)],
    ).limit(20)
    recent_logs = []
    async for doc in cursor:
        doc["_id"] = str(doc["_id"])
        recent_logs.append(doc)

    return {
        "total_calls": total_calls,
        "total_tokens": total_tokens,
        "by_model": by_model,
        "recent_logs": recent_logs,
    }


@router.post("/seed_gate/{pet_id}", tags=["admin"])
async def seed_gate_open(pet_id: str):
    """테스트 계정 gate=open 강제 세팅 (개발/시연 전용).

    - 14일치 감정 체크인(score=9, risk=0) MongoDB + Redis에 삽입
    - 35개 완료 미션 14일에 분산 삽입
    - 프로덕션 환경에서는 403 반환
    """
    if settings.APP_ENV == "production":
        raise HTTPException(
            status_code=403, detail="프로덕션 환경에서는 사용할 수 없습니다."
        )
    today = datetime.now(timezone.utc).replace(
        hour=12, minute=0, second=0, microsecond=0
    )

    # 감정 체크인 — 기존 삭제 후 14일치 삽입
    emotions_col = mongodb.db["emotions"]
    await emotions_col.delete_many({"pet_id": pet_id})
    emotion_docs = [
        {
            "pet_id": pet_id,
            "score": 9,
            "risk_level": 0,
            "note": "",
            "created_at": today - timedelta(days=13 - i),
        }
        for i in range(14)
    ]
    await emotions_col.insert_many(emotion_docs)

    # Redis — 최근 7개 세팅
    r = get_redis()
    key = f"pet:{pet_id}:emotions:recent"
    await r.delete(key)
    for i in range(7):
        entry = json.dumps(
            {
                "score": 9,
                "risk_level": 0,
                "created_at": (today - timedelta(days=6 - i)).isoformat(),
            }
        )
        await r.rpush(key, entry)
    await r.expire(key, 86400 * 30)

    # 미션 — 기존 삭제 후 35개 (14일 분산) 삽입
    missions_col = mongodb.db["missions"]
    await missions_col.delete_many({"pet_id": pet_id})
    mission_docs = []
    categories = ["신체", "감성", "추모", "휴식", "기록"]
    for i in range(35):
        day = today - timedelta(days=13 - (i % 14))
        mission_docs.append(
            {
                "pet_id": pet_id,
                "title": f"회복 미션 {i + 1}",
                "description": "시연용 완료 미션",
                "category": categories[i % len(categories)],
                "completed": True,
                "created_at": day,
                "completed_at": day,
            }
        )
    await missions_col.insert_many(mission_docs)

    return {
        "pet_id": pet_id,
        "message": "gate=open 세팅 완료 (14일 체크인 + 35 미션)",
        "emotions_inserted": 14,
        "missions_inserted": 35,
    }
