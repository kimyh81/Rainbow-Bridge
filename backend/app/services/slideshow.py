"""슬라이드쇼 서비스 — 반려동물 사진 여러 장 → FFmpeg MP4 + BGM 자동 생성."""

import asyncio
import logging
import subprocess
import tempfile
from pathlib import Path

from bson import ObjectId

from app.db.mongodb import mongodb

logger = logging.getLogger(__name__)

_VIDEO_DIR = Path("uploads/videos")
_PHOTO_DIR = Path("uploads/media")

# 모노레포 루트 기준 BGM 경로 (frontend-rn 에셋 공유)
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
_BGM_PATH = _PROJECT_ROOT / "frontend-rn" / "assets" / "audio" / "bgm_3rd.mp3"

_MAX_PHOTOS = 10  # 슬라이드쇼에 포함할 최대 사진 수
_PHOTO_DURATION = 3  # 사진 한 장 표시 시간(초)
_FADE_DURATION = 0.5  # 크로스페이드 길이(초)
_OUTPUT_WIDTH = 1080
_OUTPUT_HEIGHT = 1920


def _collection():
    return mongodb.db["media_assets"]


def _build_xfade_filter(n: int, duration: int, fade: float) -> str:
    """n장 사진의 xfade 필터 체인을 구성합니다."""
    if n == 1:
        return f"[0:v]scale={_OUTPUT_WIDTH}:{_OUTPUT_HEIGHT}:force_original_aspect_ratio=decrease,pad={_OUTPUT_WIDTH}:{_OUTPUT_HEIGHT}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1[vout]"

    offset = duration - fade
    parts = []
    prev = "[0:v]"
    for i in range(1, n):
        tag_in = f"[{i}:v]"
        tag_out = "[vout]" if i == n - 1 else f"[x{i}]"
        xoffset = round(offset * i, 3)
        scale = (
            f"{prev}scale={_OUTPUT_WIDTH}:{_OUTPUT_HEIGHT}"
            f":force_original_aspect_ratio=decrease,"
            f"pad={_OUTPUT_WIDTH}:{_OUTPUT_HEIGHT}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1[s{i-1}];"
            f"[s{i-1}]{tag_in}"
        )
        parts.append(
            f"{scale}scale={_OUTPUT_WIDTH}:{_OUTPUT_HEIGHT}"
            f":force_original_aspect_ratio=decrease,"
            f"pad={_OUTPUT_WIDTH}:{_OUTPUT_HEIGHT}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1"
            f"[p{i}];[p{i-1 if i > 1 else 's0'}][p{i}]"
            if i > 1
            else f"xfade=transition=fade:duration={fade}:offset={xoffset}{tag_out}"
        )
        prev = f"[x{i}]" if i < n - 1 else tag_out

    # 단순하게 concat 방식으로 대체 (xfade 체인보다 안정적)
    return ""


def _run_ffmpeg_slideshow(photos: list[Path], output_path: Path) -> None:
    """FFmpeg concat 방식으로 슬라이드쇼를 생성합니다."""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, encoding="utf-8"
    ) as f:
        for photo in photos:
            f.write(f"file '{photo.resolve()}'\n")
            f.write(f"duration {_PHOTO_DURATION}\n")
        # concat demuxer는 마지막 항목에도 duration 필요
        f.write(f"file '{photos[-1].resolve()}'\n")
        list_file = Path(f.name)

    try:
        scale_filter = (
            f"scale={_OUTPUT_WIDTH}:{_OUTPUT_HEIGHT}"
            f":force_original_aspect_ratio=decrease,"
            f"pad={_OUTPUT_WIDTH}:{_OUTPUT_HEIGHT}:(ow-iw)/2:(oh-ih)/2:color=black,"
            "setsar=1,format=yuv420p"
        )

        cmd: list[str] = [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(list_file),
        ]

        if _BGM_PATH.exists():
            cmd += ["-stream_loop", "-1", "-i", str(_BGM_PATH)]
            cmd += [
                "-vf",
                scale_filter,
                "-c:v",
                "libx264",
                "-preset",
                "fast",
                "-crf",
                "23",
                "-r",
                "30",
                "-c:a",
                "aac",
                "-b:a",
                "128k",
                "-shortest",
                str(output_path),
            ]
        else:
            logger.warning("BGM 파일 없음, 무음 슬라이드쇼 생성: %s", _BGM_PATH)
            cmd += [
                "-vf",
                scale_filter,
                "-c:v",
                "libx264",
                "-preset",
                "fast",
                "-crf",
                "23",
                "-r",
                "30",
                "-an",
                str(output_path),
            ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            raise RuntimeError(f"FFmpeg 오류:\n{result.stderr[-2000:]}")

    finally:
        list_file.unlink(missing_ok=True)


async def run_slideshow(pet_id: str, asset_id: str) -> None:
    """pet_id에 등록된 사진들로 슬라이드쇼 MP4를 백그라운드 생성합니다.

    완료 시 media_assets 도큐먼트에 slideshow_url, status=done 저장.
    실패 시 status=error 저장.
    """
    try:
        _VIDEO_DIR.mkdir(parents=True, exist_ok=True)

        # 1. 사진 수집 (최신순, 최대 _MAX_PHOTOS장)
        docs = (
            await _collection()
            .find({"pet_id": pet_id, "source_url": {"$ne": None}})
            .sort("created_at", -1)
            .to_list(length=_MAX_PHOTOS)
        )

        photos: list[Path] = []
        for doc in docs:
            p = Path(doc["source_url"].lstrip("/"))
            if p.exists() and p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}:
                photos.append(p)

        if not photos:
            raise ValueError("사용 가능한 사진 없음 (pet_id=%s)" % pet_id)

        output_path = _VIDEO_DIR / f"slideshow_{asset_id}.mp4"

        await asyncio.to_thread(_run_ffmpeg_slideshow, photos, output_path)

        await _collection().update_one(
            {"_id": ObjectId(asset_id)},
            {
                "$set": {
                    "slideshow_url": f"/uploads/videos/slideshow_{asset_id}.mp4",
                    "status": "done",
                }
            },
        )
        logger.info("슬라이드쇼 생성 완료 asset_id=%s photos=%d", asset_id, len(photos))

    except Exception:
        logger.exception("슬라이드쇼 생성 실패 asset_id=%s", asset_id)
        await _collection().update_one(
            {"_id": ObjectId(asset_id)},
            {"$set": {"status": "error"}},
        )
