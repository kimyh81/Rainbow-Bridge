from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class EmotionCreate(BaseModel):
    pet_id: str = Field(..., description="반려동물 ID")
    score: int = Field(
        ..., ge=1, le=10, description="감정 점수 (1=매우 힘듦, 10=괜찮음)"
    )
    note: Optional[str] = Field(None, description="감정 메모")
    sleep_quality: Optional[int] = Field(
        None, ge=1, le=5, description="수면 질 (1=매우 나쁨, 5=매우 좋음)"
    )


class EmotionResponse(BaseModel):
    id: str
    pet_id: str
    score: int
    note: Optional[str]
    risk_level: int = Field(..., description="위기 수준 (0=정상, 1=주의, 2=위기)")
    created_at: datetime
    crisis_message: Optional[str] = Field(
        None, description="위기 감지 시 1393 안내 메시지"
    )


class RecoveryResponse(BaseModel):
    pet_id: str
    total_checkins: int = Field(..., description="최근 체크인 횟수 (최대 7회)")
    avg_score: Optional[float] = Field(None, description="평균 감정 점수")
    trend: str = Field(
        ..., description="회복 추이: 회복 중 / 유지 중 / 주의 필요 / 데이터 없음"
    )
    recovery_pct: int = Field(..., description="회복률 0~100%")
    latest_risk_level: Optional[int] = Field(None, description="가장 최근 위기 수준")
    records: list[Any] = Field(
        default_factory=list, description="최근 체크인 기록 목록"
    )
    content_unlocked: bool = Field(
        False,
        description="추모 컨텐츠 공개 여부 — 회복 게이트 통과 시 True",
    )
    allow_first_person: bool = Field(
        False,
        description="1인칭 편지 허용 여부 — content_unlocked + 창 내 위기 기록 없음(max_risk=0)",
    )
    gif_unlocked: bool = Field(
        False,
        description="GIF 해금 여부 — 20점 이상",
    )
    gate_status: str = Field(
        "locked",
        description="회복 게이트 단계: locked(0~44) / teaser(45~79) / open(80+)",
    )
