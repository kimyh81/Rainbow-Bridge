"""LivePortrait 추론 HTTP 서비스 — GPU 서버(정환주)에서 실행.

백엔드(NCP)가 터널(ngrok/cloudflared 등)로 사진을 보내면, 이 서비스가
GPU 로 무음 추모 영상(mp4)을 생성해 돌려줍니다.

구조:
    [NCP 백엔드]  --(사진 POST, 터널)-->  [GPU 서버: 이 server.py]
                  <--(무음 mp4)----------   generate_video() (GPU)
    음성 합치기(merge_audio, ffmpeg)·PERSO 는 백엔드에서 처리 (GPU 불필요).

⚠️ 윤리: 무음 영상(잔잔)만 생성. 립싱크/더빙은 백엔드의 선택형 후처리 단계.

실행 (GPU 서버, conda liveportrait 환경):
    pip install fastapi uvicorn python-multipart
    cd ai/liveportrait
    uvicorn server:app --host 0.0.0.0 --port 8001
    # 그리고 터널: ngrok http 8001  (URL 을 백엔드 LIVEPORTRAIT_REMOTE_URL 에 설정)

이 서버 자신은 LIVEPORTRAIT_MODE=local (기본) 로 실제 GPU 추론을 합니다.
driving 영상은 LIVEPORTRAIT_DRIVING 으로 지정(없으면 예제 d0).
"""
from __future__ import annotations

import os
import sys
import tempfile
import uuid
from pathlib import Path

import asyncio
from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from starlette.concurrency import run_in_threadpool

# server.py 와 pipeline.py 가 같은 폴더 → 직접 import 되도록 경로 보장.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from pipeline import DRIVING_MULTIPLIER, LivePortraitError, generate_gif, generate_video  # noqa: E402

app = FastAPI(title="LivePortrait 추론 서비스", version="1.0")

# GPU 동시 추론 1건 제한 — RTX 3080 단일 GPU, 큐 쌓이면 300s 타임아웃 악순환 방지.
_gpu_sem = asyncio.Semaphore(1)

# 비동기 GIF job 인메모리 저장소 — Cloudflare 100초 타임아웃 우회용.
# { job_id: {"status": "processing"|"done"|"error", "path": Path|None} }
_gif_jobs: dict[str, dict[str, Any]] = {}

# 생성 결과 임시 저장 폴더 (GPU 서버 로컬).
_WORK_DIR = Path(tempfile.gettempdir()) / "liveportrait_service"
_WORK_DIR.mkdir(parents=True, exist_ok=True)

# 허용 이미지 확장자 (cv2 가 읽는 일반 포맷).
_ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


@app.get("/health")
def health() -> dict:
    """헬스 체크 — 터널·서비스 살아있는지 확인용."""
    return {
        "status": "ok",
        "service": "liveportrait",
        "mode": os.getenv("LIVEPORTRAIT_MODE", "local"),
        "driving_multiplier": DRIVING_MULTIPLIER,
    }


@app.post("/generate")
async def generate(source: UploadFile = File(...)) -> FileResponse:
    """반려동물 사진 → 무음 추모 영상(mp4). 영상 파일을 그대로 반환.

    driving 은 서버 기본값(LIVEPORTRAIT_DRIVING)을 사용합니다.
    """
    # 확장자 검증 + 한글/비ASCII 파일명 회피 → 안전한 영문 임시 파일명으로 저장.
    # (cv2.imread 가 Windows 비ASCII 경로를 못 읽는 이슈 회피 — EXPERIMENT.md 참고)
    ext = Path(source.filename or "").suffix.lower() or ".jpg"
    if ext not in _ALLOWED_EXT:
        raise HTTPException(status_code=400, detail=f"지원하지 않는 이미지 형식: {ext}")

    job_id = uuid.uuid4().hex[:12]
    src_path = _WORK_DIR / f"src_{job_id}{ext}"
    out_dir = _WORK_DIR / job_id

    contents = await source.read()
    if not contents:
        raise HTTPException(status_code=400, detail="빈 파일입니다.")
    src_path.write_bytes(contents)

    try:
        await asyncio.wait_for(_gpu_sem.acquire(), timeout=10.0)
    except asyncio.TimeoutError:
        src_path.unlink(missing_ok=True)
        raise HTTPException(status_code=503, detail="GPU 처리 중입니다. 잠시 후 다시 시도하세요.")

    try:
        # 블로킹(subprocess) 호출 → 스레드풀에서 실행해 이벤트 루프 안 막음.
        result_path = await run_in_threadpool(
            generate_video, src_path, output_dir=str(out_dir)
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except LivePortraitError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    finally:
        _gpu_sem.release()
        src_path.unlink(missing_ok=True)  # 입력 사진은 바로 정리

    return FileResponse(
        path=str(result_path),
        media_type="video/mp4",
        filename=result_path.name,
    )


@app.post("/generate/gif")
async def generate_memorial_gif(source: UploadFile = File(...)) -> FileResponse:
    """반려동물 사진 → 추모 GIF (d9 잔잔한 드라이빙). GIF 파일을 그대로 반환.

    입모양 없이 눈·고개 움직임만 — 치료적 목적의 첫 번째 LP 단계.
    """
    ext = Path(source.filename or "").suffix.lower() or ".jpg"
    if ext not in _ALLOWED_EXT:
        raise HTTPException(status_code=400, detail=f"지원하지 않는 이미지 형식: {ext}")

    job_id = uuid.uuid4().hex[:12]
    src_path = _WORK_DIR / f"src_{job_id}{ext}"
    out_dir = _WORK_DIR / job_id

    contents = await source.read()
    if not contents:
        raise HTTPException(status_code=400, detail="빈 파일입니다.")
    src_path.write_bytes(contents)

    try:
        await asyncio.wait_for(_gpu_sem.acquire(), timeout=10.0)
    except asyncio.TimeoutError:
        src_path.unlink(missing_ok=True)
        raise HTTPException(status_code=503, detail="GPU 처리 중입니다. 잠시 후 다시 시도하세요.")

    try:
        result_path = await run_in_threadpool(
            generate_gif, src_path, str(out_dir)
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except LivePortraitError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    finally:
        _gpu_sem.release()
        src_path.unlink(missing_ok=True)

    return FileResponse(
        path=str(result_path),
        media_type="image/gif",
        filename=result_path.name,
    )


@app.post("/generate/gif/async")
async def generate_memorial_gif_async(source: UploadFile = File(...)) -> dict:
    """비동기 GIF 생성 — job_id 즉시 반환, Cloudflare 100초 타임아웃 우회용.

    백엔드는 job_id를 받은 뒤 /generate/gif/status/{job_id} 를 폴링하고
    done 상태가 되면 /generate/gif/result/{job_id} 로 GIF를 내려받습니다.
    """
    ext = Path(source.filename or "").suffix.lower() or ".jpg"
    if ext not in _ALLOWED_EXT:
        raise HTTPException(status_code=400, detail=f"지원하지 않는 이미지 형식: {ext}")

    job_id = uuid.uuid4().hex[:12]
    src_path = _WORK_DIR / f"src_{job_id}{ext}"
    out_dir = _WORK_DIR / job_id

    contents = await source.read()
    if not contents:
        raise HTTPException(status_code=400, detail="빈 파일입니다.")
    src_path.write_bytes(contents)

    _gif_jobs[job_id] = {"status": "processing", "path": None}
    asyncio.create_task(_run_gif_job(job_id, src_path, out_dir))
    return {"job_id": job_id}


@app.get("/generate/gif/status/{job_id}")
async def gif_job_status(job_id: str) -> dict:
    """비동기 GIF job 상태 조회."""
    job = _gif_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job을 찾을 수 없습니다.")
    return {"job_id": job_id, "status": job["status"]}


@app.get("/generate/gif/result/{job_id}")
async def gif_job_result(job_id: str) -> FileResponse:
    """완성된 GIF 반환 후 job 정리."""
    job = _gif_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job을 찾을 수 없습니다.")
    if job["status"] != "done":
        raise HTTPException(status_code=400, detail=f"아직 처리 중입니다: {job['status']}")
    result_path: Path = job["path"]
    del _gif_jobs[job_id]
    return FileResponse(
        path=str(result_path),
        media_type="image/gif",
        filename=result_path.name,
    )


async def _run_gif_job(job_id: str, src_path: Path, out_dir: Path) -> None:
    """GIF job 백그라운드 처리 — 세마포어로 GPU 단일 처리 보장."""
    try:
        await asyncio.wait_for(_gpu_sem.acquire(), timeout=10.0)
    except asyncio.TimeoutError:
        src_path.unlink(missing_ok=True)
        _gif_jobs[job_id] = {"status": "error", "path": None}
        return

    try:
        result_path = await run_in_threadpool(generate_gif, src_path, str(out_dir))
        _gif_jobs[job_id] = {"status": "done", "path": result_path}
    except Exception:
        _gif_jobs[job_id] = {"status": "error", "path": None}
    finally:
        _gpu_sem.release()
        src_path.unlink(missing_ok=True)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8001")))
