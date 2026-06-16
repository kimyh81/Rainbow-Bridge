from typing import Any, Optional

from pydantic import BaseModel, Field


class EmotionTrend(BaseModel):
    created_at: str
    score: int


class PlayTrend(BaseModel):
    date: str
    count: int


class SleepTrend(BaseModel):
    date: str
    hours: float


class ReportResponse(BaseModel):
    pet_id: str
    period: Optional[str] = Field(None, description="집계 기간 (예: 2026-06)")
    usage: dict[str, Any] = Field(default_factory=dict, description="LLM 사용 횟수")
    emotion_trend: list[EmotionTrend] = Field(
        default_factory=list, description="감정 추이"
    )
    sleep_trend: list[SleepTrend] = Field(
        default_factory=list, description="수면 시간 추이"
    )
    play_trend: list[PlayTrend] = Field(
        default_factory=list, description="TTS 재생 이벤트 날짜별 횟수"
    )
    mission_completion_rate: Optional[float] = Field(
        None, description="미션 완료율 0~1"
    )
    recovery_signal: Optional[dict[str, Any]] = Field(
        None,
        description="일상복귀 신호(정량) — signal/recovery_index/emotion/access_trend/evidence 등",
    )
    revisit: Optional[int] = Field(None, description="재방문 횟수 (추후 추가)")
    play_count: Optional[int] = Field(None, description="영상 재생 횟수")
    session_count: Optional[int] = Field(None, description="로그인 접속 횟수")
