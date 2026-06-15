"""생활패턴(15%) 축 DB 배선 — health_logs(걸음·수면) + usage_stats(야간 사용량).

회복 게이트(emotion.py)·리포트(report.py) 양쪽이 공유하는 조회 헬퍼.
실제 합성(가중치·개인화)은 ai.evaluation.health_signal.lifestyle_pct (순수함수)에
맡기고, 여기서는 DB 조회 + 입력 정리만 한다.
"""

from __future__ import annotations

import app.core.ai_path  # noqa: F401  프로젝트 루트를 sys.path에 추가

from bson import ObjectId
from bson.errors import InvalidId

from ai.evaluation.health_signal import lifestyle_pct
from app.db.mongodb import mongodb

_HISTORY_DAYS = 7  # 개인화(sleep_pattern_score/night_usage_pattern_score) 기준 최근 N일


async def get_lifestyle_pct(pet_id: str) -> float | None:
    """생활패턴(15%) 축 합성 점수(0~100). 데이터가 전혀 없으면 None(무페널티 제외)."""
    health_docs = (
        await mongodb.db["health_logs"]
        .find({"pet_id": pet_id})
        .sort("date", -1)
        .to_list(_HISTORY_DAYS + 1)
    )
    if not health_docs:
        return None

    today, history_docs = health_docs[0], health_docs[1:]
    sleep_history = [
        d["sleep_hours"] for d in history_docs if d.get("sleep_hours") is not None
    ]

    night_minutes, night_minutes_history = await _night_usage(pet_id)

    return lifestyle_pct(
        steps=today.get("steps"),
        sleep_hours=today.get("sleep_hours"),
        night_minutes=night_minutes,
        sleep_history=sleep_history or None,
        night_minutes_history=night_minutes_history or None,
    )


async def _night_usage(pet_id: str) -> tuple[float | None, list[float]]:
    """오늘 새벽(심야) 폰사용 분 + 최근 기록(최대 _HISTORY_DAYS일).

    usage_stats 는 pet 이 아니라 **user_id** 단위로 적재되어 pets.user_id 로 조회한다.
    조회 실패(소유자 없음·컬렉션 없음 등)는 graceful 하게 (None, [])로 처리한다.
    """
    try:
        pet = await mongodb.db["pets"].find_one(
            {"_id": ObjectId(pet_id)}, {"user_id": 1}
        )
        if not pet or pet.get("user_id") is None:
            return None, []

        docs = (
            await mongodb.db["usage_stats"]
            .find({"userId": pet["user_id"]})
            .sort("date", -1)
            .to_list((_HISTORY_DAYS + 1) * 10)  # 날짜당 카테고리 여러 건 대비 여유
        )
    except (InvalidId, Exception):
        return None, []

    by_date: dict[str, float] = {}
    for d in docs:
        date_key = d.get("date")
        if not date_key:
            continue
        by_date[date_key] = by_date.get(date_key, 0.0) + float(
            d.get("late_night_minutes") or 0
        )

    if not by_date:
        return None, []

    dates_sorted = sorted(by_date, reverse=True)
    today_minutes = by_date[dates_sorted[0]]
    history = [by_date[d] for d in dates_sorted[1 : 1 + _HISTORY_DAYS]]
    return today_minutes, history
