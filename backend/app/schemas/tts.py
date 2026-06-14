from pydantic import BaseModel, Field


class TtsCreate(BaseModel):
    text: str = Field(..., description="낭독할 텍스트 (보호자 대상 위로 메시지)")
    tone: str = Field(
        "female",
        description="음성 톤 (female·male·narration / 구버전: warm·calm·hopeful)",
    )
    pet_id: str = Field(..., description="반려동물 ID (로그용)")
    species: str = Field("강아지", description="반려동물 종 (강아지·고양이·기타)")


class TtsResponse(BaseModel):
    audio_url: str = Field(..., description="생성된 음성 파일 URL")
    duration: float = Field(..., description="재생 길이 (초)")
    format: str = Field("mp3", description="파일 포맷")
