from fastapi import APIRouter, Depends, HTTPException

from app.core.deps import get_current_user
from app.schemas.mission import (
    MissionComplete,
    MissionItem,
    MissionRecommendRequest,
    MissionRecommendResponse,
    MissionResponse,
)
from app.schemas.mission import MissionSkipResponse
from app.services.mission import (
    complete_mission,
    create_default_missions,
    get_missions,
    skip_mission,
)

router = APIRouter()


@router.get("/{pet_id}", response_model=list[MissionResponse])
async def list_missions(pet_id: str, user: dict = Depends(get_current_user)):
    missions = await get_missions(pet_id)
    if not missions:
        missions = await create_default_missions(pet_id)
    return missions


@router.patch("/{mission_id}/complete", response_model=MissionResponse)
async def done_mission(
    mission_id: str, body: MissionComplete, user: dict = Depends(get_current_user)
):
    mission = await complete_mission(mission_id)
    if not mission:
        raise HTTPException(status_code=404, detail="미션을 찾을 수 없습니다.")
    return mission


@router.patch("/{mission_id}/skip", response_model=MissionSkipResponse)
async def skip_mission_endpoint(
    mission_id: str, user: dict = Depends(get_current_user)
):
    skipped, replacement = await skip_mission(mission_id)
    if not skipped:
        raise HTTPException(status_code=404, detail="미션을 찾을 수 없습니다.")
    return MissionSkipResponse(skipped_mission=skipped, replacement=replacement)


# TODO: 반소람님 AI recommend() 연결 후 교체
_RECOMMEND_POOL = [
    MissionItem(
        title="오늘 5분 산책하기",
        description="짧은 산책으로 기분을 환기해요.",
        category="신체",
    ),
    MissionItem(
        title="좋아하는 음악 한 곡 듣기",
        description="좋아하는 곡 하나를 온전히 들어봐요.",
        category="감성",
    ),
    MissionItem(
        title="추억 사진 한 장 꺼내보기",
        description="함께한 사진을 꺼내 잠시 추억해요.",
        category="추모",
    ),
    MissionItem(
        title="따뜻한 음료 한 잔 마시기",
        description="따뜻한 음료로 몸과 마음을 달래요.",
        category="휴식",
    ),
    MissionItem(
        title="오늘 감정 일기 한 줄 쓰기",
        description="오늘 느낀 감정을 한 줄로 적어봐요.",
        category="기록",
    ),
    MissionItem(
        title="창문 열고 바람 맞기",
        description="신선한 공기로 환기해요.",
        category="신체",
    ),
    MissionItem(
        title="가까운 사람에게 안부 전하기",
        description="소중한 사람과 짧게 연락해요.",
        category="관계",
    ),
]


@router.post("/recommend", response_model=MissionRecommendResponse)
async def recommend_missions(body: MissionRecommendRequest):
    """AI 맞춤 미션 추천 — 반소람님 AI 연결 전 스텁."""
    count = 3 if (body.emotion_score or 5) >= 5 else 2
    return MissionRecommendResponse(
        missions=_RECOMMEND_POOL[:count],
        source="stub",
    )
