"""v1 API 라우터 통합.
각 기능 담당이 endpoints/ 아래에 라우터를 만들고 여기에 등록합니다.
예시:
    from app.api.v1.endpoints import pets
    api_router.include_router(pets.router, prefix="/pets", tags=["pets"])
"""

from fastapi import APIRouter
from app.api.v1.endpoints import (
    funerals,
    admin,
    vets,
    diaries,
    auth,
    emotions,
    health,
    hospitals,
    llm_logs,
    media,
    messages,
    missions,
    pets,
    play_logs,
    report,
    timeline,
    tts,
    terminal_care,
)

api_router = APIRouter()
# ===== 기능별 라우터 등록 =====
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(pets.router, prefix="/pets", tags=["pets"])
api_router.include_router(emotions.router, prefix="/emotions", tags=["emotions"])
api_router.include_router(missions.router, prefix="/missions", tags=["missions"])
api_router.include_router(messages.router, prefix="/messages", tags=["messages"])
api_router.include_router(tts.router, prefix="/tts", tags=["tts"])
api_router.include_router(play_logs.router, prefix="/play-logs", tags=["play_logs"])
api_router.include_router(report.router, prefix="/report", tags=["report"])
api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(timeline.router, prefix="/timeline", tags=["timeline"])
api_router.include_router(llm_logs.router, prefix="/llm-logs", tags=["llm_logs"])
api_router.include_router(funerals.router, prefix="/funerals", tags=["funerals"])
api_router.include_router(hospitals.router, prefix="/hospitals", tags=["hospitals"])
api_router.include_router(media.router, prefix="/media", tags=["media"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
api_router.include_router(vets.router, prefix="/vets", tags=["vets"])
api_router.include_router(diaries.router, prefix="/diaries", tags=["diaries"])
api_router.include_router(
    terminal_care.router, prefix="/terminal-care", tags=["terminal_care"]
)
