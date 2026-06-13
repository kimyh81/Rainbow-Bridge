import asyncio
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

import requests
from bson import ObjectId
from bson.errors import InvalidId

from app.core.config import settings
from app.db.mongodb import mongodb

logger = logging.getLogger(__name__)

_PERSO_BASE = "https://api.perso.ai"
_PERSO_KEY = os.getenv("PERSO_API_KEY", "")
_PERSO_SPACE = int(os.getenv("PERSO_SPACE_SEQ", "0"))
_PERSO_HEADERS = {"XP-API-KEY": _PERSO_KEY, "Content-Type": "application/json"}

_UPLOAD_DIR = Path("uploads/media")
_VIDEO_DIR = Path("uploads/videos")
_TTS_DIR = Path("uploads/tts")


def _collection():
    return mongodb.db["media_assets"]


def _to_object_id(asset_id: str) -> ObjectId | None:
    try:
        return ObjectId(asset_id)
    except (InvalidId, TypeError):
        return None


async def create_asset(pet_id: str, source_path: str, user_id: int) -> str:
    doc = {
        "pet_id": pet_id,
        "user_id": user_id,
        "source_url": f"/uploads/media/{Path(source_path).name}",
        "status": "processing",
        "video_url": None,
        "created_at": datetime.now(timezone.utc),
    }
    result = await _collection().insert_one(doc)
    return str(result.inserted_id)


async def get_asset(asset_id: str, user_id: int | None = None) -> dict | None:
    oid = _to_object_id(asset_id)
    if oid is None:
        return None
    query: dict = {"_id": oid}
    if user_id is not None:
        query["user_id"] = user_id
    doc = await _collection().find_one(query)
    if not doc:
        return None
    return {
        "asset_id": str(doc["_id"]),
        "status": doc["status"],
        "gif_url": doc.get("gif_url"),
        "video_url": doc.get("video_url"),
        "voiced_url": doc.get("voiced_url"),
        "dubbed_url": doc.get("dubbed_url"),
    }


async def trigger_liveportrait_for_pet(pet_id: str) -> None:
    """1인칭 편지 허용 시 d3 입모양 영상 백그라운드 생성. 이미 video_url 있으면 skip."""
    try:
        doc = await _collection().find_one(
            {"pet_id": pet_id, "source_url": {"$ne": None}},
            sort=[("created_at", -1)],
        )
        if not doc:
            return
        if doc.get("video_url"):
            return
        asset_id = str(doc["_id"])
        source_path = Path(doc["source_url"].lstrip("/"))
        if source_path.exists():
            asyncio.create_task(run_liveportrait(asset_id, str(source_path), pet_id))
    except Exception:
        logger.warning("1인칭 LP 트리거 실패 pet_id=%s", pet_id, exc_info=True)


def _remote_generate_gif(source_path: str, output_dir: Path) -> Path:
    """GPU 서버 /generate/gif/async → 폴링 → 결과 저장."""
    api = settings.LIVEPORTRAIT_API_URL.rstrip("/")
    if not api:
        raise ValueError(
            "LIVEPORTRAIT_API_URL 미설정 — remote 모드에서는 GPU 서버 URL이 필요합니다."
        )

    with open(source_path, "rb") as f:
        resp = requests.post(
            f"{api}/generate/gif/async", files={"source": f}, timeout=30
        )
    resp.raise_for_status()
    job_id = resp.json()["job_id"]

    for _ in range(72):  # 최대 6분 폴링
        time.sleep(5)
        st = requests.get(f"{api}/generate/gif/status/{job_id}", timeout=10)
        if st.json().get("status") == "done":
            break

    result = requests.get(f"{api}/generate/gif/result/{job_id}", timeout=30)
    result.raise_for_status()
    out_path = output_dir / f"{Path(source_path).stem}_remote.gif"
    out_path.write_bytes(result.content)
    return out_path


def _remote_generate_video(source_path: str, output_dir: Path) -> Path:
    """GPU 서버 /generate → MP4 다운로드."""
    api = settings.LIVEPORTRAIT_API_URL.rstrip("/")
    if not api:
        raise ValueError(
            "LIVEPORTRAIT_API_URL 미설정 — remote 모드에서는 GPU 서버 URL이 필요합니다."
        )
    with open(source_path, "rb") as f:
        resp = requests.post(f"{api}/generate", files={"source": f}, timeout=120)
    resp.raise_for_status()
    out_path = output_dir / f"{Path(source_path).stem}_remote.mp4"
    out_path.write_bytes(resp.content)
    return out_path


async def run_liveportrait_gif(
    asset_id: str, source_path: str, set_status: bool = False
):
    """백그라운드에서 GIF 생성 (d9 잔잔한 드라이빙).

    set_status=True: driving_type=gif 직접 호출 시 status를 done/error로 갱신.
    set_status=False: voiced 완료 후 보조 생성 시 status 건드리지 않음.
    """
    try:
        _VIDEO_DIR.mkdir(parents=True, exist_ok=True)

        import sys

        repo_root = str(Path(__file__).resolve().parents[3])
        if repo_root not in sys.path:
            sys.path.insert(0, repo_root)

        if settings.LIVEPORTRAIT_MODE == "remote" and settings.LIVEPORTRAIT_API_URL:
            gif_path = await asyncio.to_thread(
                _remote_generate_gif, source_path, _VIDEO_DIR
            )
        else:
            from ai.liveportrait.pipeline import generate_gif

            gif_path = await asyncio.to_thread(
                generate_gif, source_path, str(_VIDEO_DIR)
            )

        update: dict = {"gif_url": f"/uploads/videos/{gif_path.name}"}
        if set_status:
            update["status"] = "done"
        await _collection().update_one(
            {"_id": ObjectId(asset_id)},
            {"$set": update},
        )
    except Exception:
        logger.exception("GIF 생성 실패 asset_id=%s", asset_id)
        if set_status:
            await _collection().update_one(
                {"_id": ObjectId(asset_id)},
                {"$set": {"status": "error"}},
            )


async def run_liveportrait(asset_id: str, source_path: str, pet_id: str = ""):
    """백그라운드에서 LivePortrait 실행. 실패 시 status=error로 처리."""
    try:
        _VIDEO_DIR.mkdir(parents=True, exist_ok=True)

        import sys

        repo_root = str(Path(__file__).resolve().parents[3])
        if repo_root not in sys.path:
            sys.path.insert(0, repo_root)

        if settings.LIVEPORTRAIT_MODE == "remote" and settings.LIVEPORTRAIT_API_URL:
            video_path = await asyncio.to_thread(
                _remote_generate_video, source_path, _VIDEO_DIR
            )
        else:
            from ai.liveportrait.pipeline import generate_video

            video_path = await asyncio.to_thread(
                generate_video, source_path, output_dir=str(_VIDEO_DIR)
            )

        from ai.liveportrait.pipeline import merge_audio

        # 2. TTS 음성 있으면 합치기 (pet_id를 인수로 받아 DB 재조회 불필요)
        if not pet_id:
            doc = await _collection().find_one({"_id": ObjectId(asset_id)})
            pet_id = doc.get("pet_id", "") if doc else ""
        tts_files = sorted(
            [*_TTS_DIR.glob(f"{pet_id}_*.mp3"), *_TTS_DIR.glob(f"{pet_id}_*.wav")],
            key=lambda f: f.stat().st_mtime,
            reverse=True,
        )

        voiced_path = None
        if tts_files:
            output_path = _VIDEO_DIR / f"{Path(video_path).stem}_voiced.mp4"
            voiced_path = await asyncio.to_thread(
                merge_audio, video_path, str(tts_files[0]), output_path=output_path
            )

        update = {
            "status": "done",
            "video_url": f"/uploads/videos/{Path(video_path).name}",
            "voiced_url": (
                f"/uploads/videos/{Path(voiced_path).name}" if voiced_path else None
            ),
        }

        await _collection().update_one(
            {"_id": ObjectId(asset_id)},
            {
                "$set": update,
            },
        )
        # MP4 완료 후 GIF 백그라운드 생성
        asyncio.create_task(run_liveportrait_gif(asset_id, source_path))
    except Exception:
        logger.exception("LivePortrait 처리 실패 asset_id=%s", asset_id)
        await _collection().update_one(
            {"_id": ObjectId(asset_id)},
            {"$set": {"status": "error"}},
        )


async def run_perso(asset_id: str):
    """voiced_url 영상을 PERSO에 업로드 → 더빙 → dubbed_url 저장."""
    try:
        doc = await _collection().find_one({"_id": ObjectId(asset_id)})
        if not doc or not doc.get("voiced_url"):
            return

        # voiced_url → 로컬 파일 경로 복원
        voiced_url = doc["voiced_url"]  # e.g. /uploads/videos/xxx.mp4
        local_path = Path(voiced_url.lstrip("/"))
        if not local_path.exists():
            raise FileNotFoundError(f"{local_path} 없음")

        def _upload_and_dub():
            file_name = local_path.name
            # 1. SAS 토큰
            sas = requests.get(
                f"{_PERSO_BASE}/file/api/upload/sas-token?fileName={quote(file_name)}",
                headers=_PERSO_HEADERS,
            ).json()
            blob_url = (sas.get("result") or sas)["blobSasUrl"]

            # 2. Azure 업로드
            with open(local_path, "rb") as f:
                requests.put(
                    blob_url,
                    data=f,
                    headers={
                        "x-ms-blob-type": "BlockBlob",
                        "Content-Type": "application/octet-stream",
                    },
                ).raise_for_status()

            # 3. 미디어 등록
            reg = requests.put(
                f"{_PERSO_BASE}/file/api/upload/video",
                headers=_PERSO_HEADERS,
                json={
                    "spaceSeq": _PERSO_SPACE,
                    "fileUrl": blob_url.split("?")[0],
                    "fileName": file_name,
                },
            ).json()
            media_seq = (reg.get("result") or reg)["seq"]

            # 4. 큐 초기화
            requests.put(
                f"{_PERSO_BASE}/video-translator/api/v1/projects/spaces/{_PERSO_SPACE}/queue",
                headers=_PERSO_HEADERS,
            )

            # 5. 프로젝트 생성
            create = requests.post(
                f"{_PERSO_BASE}/video-translator/api/v1/projects/spaces/{_PERSO_SPACE}/translate",
                headers=_PERSO_HEADERS,
                json={
                    "mediaSeq": media_seq,
                    "isVideoProject": True,
                    "sourceLanguageCode": "auto",
                    "targetLanguages": [
                        {"languageCode": "ko", "ttsModel": "ELEVEN_V2"}
                    ],
                    "preferredSpeedType": "GREEN",
                    "title": f"rb_{asset_id}_{int(time.time())}",
                },
            ).json()
            raw = create.get("result") or create
            project_id = raw.get("projectId") or raw.get("startGenerateProjectIdList")
            if isinstance(project_id, list):
                project_id = project_id[0]

            # 6. 폴링 (최대 5분)
            for _ in range(60):
                prog = requests.get(
                    f"{_PERSO_BASE}/video-translator/api/v1/projects/{project_id}/space/{_PERSO_SPACE}/progress",
                    headers=_PERSO_HEADERS,
                ).json()
                status = (prog.get("result") or prog).get("progressReason") or ""
                if status == "Completed":
                    break
                if status == "Failed":
                    raise RuntimeError("PERSO 작업 실패")
                time.sleep(5)

            # 7. 다운로드 링크
            link = requests.get(
                f"{_PERSO_BASE}/video-translator/api/v1/projects/{project_id}/spaces/{_PERSO_SPACE}/download?target=dubbingVideo",
                headers=_PERSO_HEADERS,
            ).json()
            path = (
                (link.get("result") or {}).get("videoFile", {}).get("videoDownloadLink")
            )
            if path and path.startswith("/"):
                path = f"https://perso-saas-file-frontdoor.perso.ai{path}"

            # 8. 저장
            save_name = f"dubbed_{asset_id}.mp4"
            save_path = _VIDEO_DIR / save_name
            with requests.get(path, headers=_PERSO_HEADERS, stream=True) as r:
                r.raise_for_status()
                with open(save_path, "wb") as f:
                    for chunk in r.iter_content(8192):
                        f.write(chunk)
            return f"/uploads/videos/{save_name}"

        dubbed_url = await asyncio.to_thread(_upload_and_dub)
        await _collection().update_one(
            {"_id": ObjectId(asset_id)},
            {"$set": {"dubbed_url": dubbed_url}},
        )
    except Exception:
        logger.exception(
            "PERSO 더빙 실패 asset_id=%s", asset_id
        )  # 메인 서비스에 영향 없음


async def select_best_pet_photo(pet_id: str) -> Path | None:
    """pet_id에 속한 업로드 사진 중 LivePortrait 적합도가 가장 높은 사진 경로를 반환."""
    docs = (
        await _collection()
        .find({"pet_id": pet_id, "source_url": {"$ne": None}})
        .to_list(length=None)
    )

    if not docs:
        return None

    paths = []
    for doc in docs:
        source_url = doc.get("source_url", "")
        local = Path(source_url.lstrip("/"))
        if local.exists():
            paths.append(local)

    if not paths:
        return None

    repo_root = str(Path(__file__).resolve().parents[3])
    import sys

    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    from ai.liveportrait.photo_selector import pick_best

    return pick_best(paths)


async def delete_asset(asset_id: str, user_id: int) -> bool:
    """사진 asset 삭제 — MongoDB 문서 + 서버 물리 파일 함께 제거."""
    oid = _to_object_id(asset_id)
    if oid is None:
        return False
    doc = await _collection().find_one({"_id": oid, "user_id": user_id})
    if not doc:
        return False
    source_url = doc.get("source_url")
    if source_url:
        source_path = Path(source_url.lstrip("/"))
        source_path.unlink(missing_ok=True)
    await _collection().delete_one({"_id": oid})
    return True


async def increment_play_count(asset_id: str) -> None:
    """영상 재생 시 play_count +1."""
    oid = _to_object_id(asset_id)
    if oid is None:
        return
    await _collection().update_one(
        {"_id": oid},
        {"$inc": {"play_count": 1}},
        upsert=False,
    )
