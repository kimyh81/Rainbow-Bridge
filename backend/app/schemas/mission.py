from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class MissionResponse(BaseModel):
    id: str
    pet_id: str
    title: str
    description: str
    category: str = ""
    rationale: Optional[str] = None
    completed: bool
    created_at: datetime
    completed_at: Optional[datetime] = None
    video_url: Optional[str] = None  # 슬라이드쇼 등 자동 생성 영상 URL


class MissionComplete(BaseModel):
    completed: bool = True


class MissionRecommendRequest(BaseModel):
    pet_id: str
    emotion_score: Optional[int] = None
    day_since: Optional[int] = None


class MissionItem(BaseModel):
    title: str
    description: str = ""
    category: str = ""
    rationale: Optional[str] = None


class MissionRecommendResponse(BaseModel):
    missions: list[MissionItem]
    source: str = "stub"
