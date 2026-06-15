from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.deps import get_current_user
from app.services.care import get_anniversary_care

router = APIRouter()


class AnniversaryCareResponse(BaseModel):
    message: str
    days_since: int
    milestone_label: str
    source: str
    crisis_message: Optional[str] = None
    risk_level: Optional[int] = None
    support_message: Optional[str] = None
    welfare_resources: Optional[list[str]] = None


@router.get("/pets/{pet_id}/anniversary", response_model=AnniversaryCareResponse)
async def anniversary_care(
    pet_id: str,
    note: str = "",
    days_since: Optional[int] = None,
    user: dict = Depends(get_current_user),
):
    """기념일(D+30·D+100) 케어 메시지를 반환합니다.

    - days_since 미입력 시: 오늘 날짜 기준 자동 확인 (기념일 아니면 404)
    - days_since 입력 시: 강제 생성 (데모·테스트용)
    """
    result = await get_anniversary_care(pet_id, note=note, days_since=days_since)
    if result is None:
        raise HTTPException(
            status_code=404, detail="오늘은 기념일이 아닙니다 (D+30 또는 D+100)."
        )
    return AnniversaryCareResponse(**result)
