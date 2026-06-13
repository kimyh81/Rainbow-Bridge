import uuid
from pathlib import Path

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
)
from fastapi.responses import FileResponse
from app.core.deps import get_current_user
from app.schemas.media import MediaStatusResponse, MediaUploadResponse
from app.services.media import (
    create_asset,
    delete_asset,
    get_asset,
    run_liveportrait,
    run_liveportrait_gif,
    run_perso,
    increment_play_count,
    select_best_pet_photo,
)
from app.services.pet import get_pet

router = APIRouter()

_UPLOAD_DIR = Path("uploads/media")
_MAX_SIZE = 10 * 1024 * 1024  # 10MB
_ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}


@router.post("/upload", response_model=MediaUploadResponse, status_code=201)
async def upload_media(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    pet_id: str = Form(...),
    user: dict = Depends(get_current_user),
):
    if not await get_pet(pet_id, user_id=user["user_id"]):
        raise HTTPException(status_code=404, detail="반려동물 정보를 찾을 수 없습니다.")

    if file.content_type not in _ALLOWED_TYPES:
        raise HTTPException(
            status_code=400, detail="이미지 파일(JPEG, PNG, WebP)만 업로드 가능합니다."
        )

    contents = await file.read()
    if len(contents) > _MAX_SIZE:
        raise HTTPException(status_code=400, detail="파일 크기는 10MB 이하여야 합니다.")

    _UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    ext = Path(file.filename).suffix if file.filename else ".jpg"
    save_path = _UPLOAD_DIR / f"{uuid.uuid4().hex}{ext}"
    save_path.write_bytes(contents)

    asset_id = await create_asset(pet_id, str(save_path), user_id=user["user_id"])

    return MediaUploadResponse(asset_id=asset_id)


@router.get("/{asset_id}", response_model=MediaStatusResponse)
async def get_media_status(asset_id: str, user: dict = Depends(get_current_user)):
    asset = await get_asset(asset_id, user_id=user["user_id"])
    if not asset:
        raise HTTPException(status_code=404, detail="asset을 찾을 수 없습니다.")
    return MediaStatusResponse(**asset)


@router.post("/{asset_id}/perso", status_code=202)
async def request_perso(
    asset_id: str,
    background_tasks: BackgroundTasks,
    user: dict = Depends(get_current_user),
):
    """PERSO 다국어 더빙 비동기 요청. voiced_url 영상을 PERSO에 전송."""
    asset = await get_asset(asset_id, user_id=user["user_id"])
    if not asset:
        raise HTTPException(status_code=404, detail="asset을 찾을 수 없습니다.")
    if not asset.get("voiced_url"):
        raise HTTPException(
            status_code=400, detail="영상+음성 합치기가 완료되지 않았습니다."
        )

    background_tasks.add_task(run_perso, asset_id)
    return {
        "message": "PERSO 더빙 요청이 접수됐습니다.",
        "asset_id": asset_id,
        "status": "pending",
    }


@router.get("/{asset_id}/download")
async def download_media(
    asset_id: str,
    type: str = "video",
    user: dict = Depends(get_current_user),
):
    """미디어 파일 다운로드. type: video | voiced | dubbed"""
    asset = await get_asset(asset_id, user_id=user["user_id"])
    if not asset:
        raise HTTPException(status_code=404, detail="asset을 찾을 수 없습니다.")

    url_map = {
        "video": asset.get("video_url"),
        "voiced": asset.get("voiced_url"),
        "dubbed": asset.get("dubbed_url"),
    }

    if type not in url_map:
        raise HTTPException(
            status_code=400, detail="type은 video | voiced | dubbed 중 하나여야 합니다."
        )

    file_url = url_map[type]
    if not file_url:
        raise HTTPException(status_code=404, detail="아직 파일이 준비되지 않았습니다.")

    file_path = Path(file_url.lstrip("/"))
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다.")

    return FileResponse(
        path=file_path,
        media_type="video/mp4",
        filename=f"{asset_id}_{type}.mp4",
    )


@router.post("/generate/{pet_id}", status_code=202)
async def generate_memorial_video(
    pet_id: str,
    background_tasks: BackgroundTasks,
    driving_type: str = Query("voiced", pattern="^(gif|voiced)$"),
    user: dict = Depends(get_current_user),
):
    """저장된 사진 중 LivePortrait 적합도 최고 사진을 자동 선택해 추모 영상 생성.

    업로드된 모든 사진을 선명도·밝기·해상도·종횡비로 채점 후 최적 사진으로 영상 생성.
    생성은 비동기(백그라운드)로 진행되며, asset_id로 진행 상태 조회 가능.
    """
    if not await get_pet(pet_id, user_id=user["user_id"]):
        raise HTTPException(status_code=404, detail="반려동물 정보를 찾을 수 없습니다.")

    best_photo = await select_best_pet_photo(pet_id)
    if best_photo is None:
        raise HTTPException(
            status_code=404,
            detail="사용 가능한 사진이 없습니다. 먼저 사진을 업로드해주세요.",
        )

    asset_id = await create_asset(pet_id, str(best_photo), user_id=user["user_id"])
    if driving_type == "gif":
        background_tasks.add_task(run_liveportrait_gif, asset_id, str(best_photo), True)
    else:
        background_tasks.add_task(run_liveportrait, asset_id, str(best_photo), pet_id)

    return {
        "asset_id": asset_id,
        "message": "추모 영상 생성이 시작됐습니다.",
        "selected_photo": best_photo.name,
        "driving_type": driving_type,
    }


@router.get("/{asset_id}/gif")
async def download_gif(asset_id: str, user: dict = Depends(get_current_user)):
    """추모 GIF 다운로드 (① 단계 — d9 잔잔한 드라이빙)."""
    asset = await get_asset(asset_id, user_id=user["user_id"])
    if not asset:
        raise HTTPException(status_code=404, detail="asset을 찾을 수 없습니다.")

    gif_url = asset.get("gif_url")
    if not gif_url:
        raise HTTPException(status_code=404, detail="GIF가 아직 준비되지 않았습니다.")

    gif_path = Path(gif_url.lstrip("/"))
    if not gif_path.exists():
        raise HTTPException(status_code=404, detail="GIF 파일을 찾을 수 없습니다.")

    return FileResponse(
        path=gif_path,
        media_type="image/gif",
        filename=f"{asset_id}.gif",
    )


@router.delete("/{asset_id}", status_code=204)
async def delete_media(asset_id: str, user: dict = Depends(get_current_user)):
    """사진 삭제 — MongoDB 문서 + 서버 파일 함께 제거."""
    deleted = await delete_asset(asset_id, user_id=user["user_id"])
    if not deleted:
        raise HTTPException(status_code=404, detail="asset을 찾을 수 없습니다.")


@router.post("/{asset_id}/play", status_code=200)
async def record_play(asset_id: str, user: dict = Depends(get_current_user)):
    """영상 재생 시 호출 — play_count +1 기록."""
    asset = await get_asset(asset_id, user_id=user["user_id"])
    if not asset:
        raise HTTPException(status_code=404, detail="asset을 찾을 수 없습니다.")
    await increment_play_count(asset_id)
    return {"asset_id": asset_id, "message": "재생 기록 완료"}
