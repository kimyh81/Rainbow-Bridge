"""기념일 케어 서비스 — D+30·D+100 시점 보호자 케어 메시지 생성.

ai.llm.anniversary.generate_anniversary_care 를 백엔드 DB 조회와 연결합니다.
period 문자열("2018-01-01 ~ 2026-06-01")의 마지막 날짜를 farewell_date 로 사용합니다.
"""

from __future__ import annotations

import app.core.ai_path  # noqa: F401

from datetime import date
from typing import Optional

from bson import ObjectId

from ai.llm.anniversary import check_anniversary, generate_anniversary_care
from ai.llm.provider import generate
from app.db.mongodb import mongodb


def _parse_farewell_date(period: Optional[str]) -> Optional[date]:
    """period 문자열에서 마지막 날짜(farewell date)를 파싱합니다.

    예: "2018-01-01 ~ 2026-06-01" → date(2026, 6, 1)
    """
    if not period:
        return None
    try:
        raw = period.split("~")[-1].strip()
        return date.fromisoformat(raw)
    except (ValueError, IndexError):
        return None


async def get_anniversary_care(
    pet_id: str,
    *,
    note: str = "",
    days_since: Optional[int] = None,
) -> Optional[dict]:
    """기념일 케어 메시지를 반환합니다.

    Args:
        pet_id: 반려동물 ID.
        note: 보호자 감정 메모 (선택). 위기 선체크에도 사용.
        days_since: 강제 지정 시 check_anniversary 생략 (데모·테스트용).
            None 이면 오늘 날짜 기준으로 D+30·D+100 자동 확인.

    Returns:
        케어 메시지 dict 또는 None (오늘 기념일 아닌 경우).
    """
    doc = await mongodb.db["pets"].find_one({"_id": ObjectId(pet_id)})
    if not doc:
        return None

    pet = {
        "name": doc.get("name", ""),
        "species": doc.get("species", ""),
        "memories": doc.get("memories"),
    }

    if days_since is None:
        farewell_date = _parse_farewell_date(doc.get("period"))
        if not farewell_date:
            return None
        days_since = check_anniversary(farewell_date, date.today())
        if days_since is None:
            return None

    return generate_anniversary_care(
        pet=pet,
        days_since=days_since,
        note=note,
        generate=generate,
        source="local",
    )
