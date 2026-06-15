"""④ TTS 추론 HTTP 서비스 — GPU 서버(정환주)에서 실행.

NCP 백엔드엔 GPU 가 없으므로(=A안 불가), 백엔드가 텍스트를 HTTP 로 보내면
이 서비스가 GPU 로 Qwen3 합성 wav 를 만들어 돌려줍니다. LivePortrait 와 동일 패턴.

구조:
    [프론트] -> POST /tts (NCP 백엔드) -> HTTP -> [GPU 서버: 이 server.py /synthesize] -> Qwen3
                                        <-- wav --

  - 정환주(GPU): 이 server.py — synthesize() 를 /synthesize 로 노출.
  - 김윤한(백엔드): /tts 에서 TTS_SERVER_URL 로 이 서비스 HTTP 호출.

윤리: 보호자 대상 위로 낭독만. 반려동물 목소리 흉내 ❌.

실행 (GPU 서버, conda qwen3-tts 환경 — __init__.py 가 google-cloud 끌어오므로 `-m` 금지):
    pip install fastapi uvicorn
    conda run --no-capture-output -n qwen3-tts python ai/tts/server.py
    # 또는: cd ai/tts && uvicorn server:app --host 0.0.0.0 --port 8002
    # 그리고 터널(URL 을 백엔드 TTS_SERVER_URL 에 설정) → 터널·동시1개 제약은 ../GPU_SERVER.md

포트 8002 — webui(8000)·liveportrait(8001) 와 겹치지 않게.
VRAM ~4.6GB(첫 /synthesize 호출 때 온디맨드 로드). webui(8000)와 동시 구동 시
8GB 초과 주의 — qwen3 인스턴스는 하나만 띄울 것(../tts/CLAUDE.md §4).
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import AliasChoices, BaseModel, Field
from starlette.concurrency import run_in_threadpool

# server.py 와 qwen3_synthesize.py 가 같은 폴더 → 직접 import 되도록 경로 보장
# (top-level 모듈로 잡혀 ai/tts/__init__.py 의 google-cloud import 를 피함).
sys.path.insert(0, str(Path(__file__).resolve().parent))

# CUDA 메모리 단편화 완화 — torch/CUDA 초기화(바로 아래 import 가 끌어옴) 전에 설정해야
# 먹는다. VRAM 빠듯(8GB 공유)할 때 남은 여유를 OOM/정체 없이 쓰게. qwen3_synthesize 의
# KMP_DUPLICATE_LIB_OK setdefault 와 동일 패턴.
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
from qwen3_synthesize import AVAILABLE_VOICES, _get_model, synthesize  # noqa: E402

# 모델 준비 상태 — health 가 노출해 백엔드/기동스크립트가 콜드스타트 중인지 구분.
_model_ready = False

# GPU 추론 직렬화(VRAM 8GB·모델 1개) — 동시 요청이 GPU 를 경합하면 각 합성이
# 4.5s→85s 로 폭증(앱 504 재시도 폭주 시 죽음의 소용돌이). 한 번에 하나만 추론해
# 각 요청을 제 속도로 끝내고 나머지는 큐 대기시킨다.
_gpu_sem = asyncio.Semaphore(1)

# 소형 대기큐: 동시요청을 즉시 503 으로 버리지 않고 GPU 슬롯을 기다리게 한다.
# max_new_tokens 상한으로 합성이 ~10s 로 묶여 있어 줄을 서도 안전해졌다(예전엔
# 한 건이 100s+ hang → 뒤가 무한대기라 fast-503 이 필요했음).
#  - _MAX_INFLIGHT: 처리중 1 + 대기 최대 3 = 4. 4×~10s≈40s 로 백엔드 60s 타임아웃 안.
#    이미 4건이 잡혀있는데 더 오면 그때만 즉시 503(과부하 차단=죽음의 소용돌이 방지).
#  - _ACQUIRE_TIMEOUT: 큐에서 이 시간 내 슬롯 못 잡으면 503(백엔드가 이미 포기했을 요청
#    에 GPU 낭비 방지). 백엔드 60s 보다 짧게.
_MAX_INFLIGHT = 4
_ACQUIRE_TIMEOUT = 40.0  # 백엔드 httpx 60s − 합성여유. 4건×~10s=40s 큐는 다 수용.
_inflight = 0

# 합성 상한 — 실측(2026-06-14 깨끗한 GPU 직접 측정): 합성시간 ≈ 0.35초/자(RTF 2.1).
# 413자=178초·586자=204초로 정상 완료(hang 아님). 옛 150초는 이 합성시간보다 짧아
# 420자↑ 메시지(memorial 강제 600자 포함)를 깨끗한 GPU에서도 무조건 잘라 _degraded→폴백
# 시키던 버그였음(과거 "stall"의 정체 = hang 아닌 150초 컷). 300초로 상향: 600자(204초)+
# 여유 수용, 백엔드 폴링 360초(tts.py) 안. 진짜 hang(드묾) 시에도 300초 후 wait_for 가
# await 끊고 _degraded→폴백(소리 유지). 스레드는 강제종료 불가라 degraded 로 2차생성 차단.
_SYNTH_TIMEOUT = 300.0

# hang 1회라도 감지되면 True. /health 가 model_ready=false 로 노출 → 워치독이 재등록
# 중단(TTL 만료로 백엔드는 .env/폴백)하고, 새 합성 요청은 즉시 503(구글 폴백→소리)로
# 받아 두 번째 생성이 시작되지 못하게 막는다(죽음의 소용돌이 방지). 재시작 전까지 유지.
_degraded = False

# ── 비동기 잡 방식(긴 메시지 대응) ───────────────────────────────────────────
# 동기 /synthesize 는 합성이 글자수에 비례(~0.33s/자)해 긴 추모 메시지(180자↑)면
# 70s+ → 백엔드 60s 타임아웃 초과로 끊김(cloudflared "context canceled")→폴백.
# LivePortrait 와 동일하게 "제출→job_id 즉시 반환 + 폴링" 으로 바꿔, 각 HTTP 호출을
# 짧게 만들어 길이·터널과 무관하게 안전하게 한다. (기존 동기 /synthesize 는 하위호환 유지)
#  - _JOBS: job_id -> {status, audio_path, duration, format, error, created}
#  - _MAX_PENDING_JOBS: 처리중(큐 포함) 상한. 넘으면 제출 즉시 503(과부하 차단).
#  - _JOB_TTL: 완료/실패 job 레코드 보존 시간(메모리 누수 방지). 파일은 안 지움.
_JOBS: dict[str, dict] = {}
_MAX_PENDING_JOBS = 8
_JOB_TTL = 600.0  # 10분

# create_task 가 돌려준 태스크는 이벤트 루프가 약참조로만 추적 → 강참조 안 잡으면
# GC 가 실행 도중 태스크를 수거할 수 있다. 그러면 잡이 processing 에 영구 고정되고,
# 합성 중 취소 시 세마포어는 풀렸는데 GPU 스레드는 계속 돌아 직렬화가 깨진다(죽음의
# 소용돌이 재발). 강참조 셋에 보관하고 완료 시 콜백으로 제거한다.
_BG_TASKS: set[asyncio.Task] = set()


def _purge_old_jobs() -> None:
    """오래된 완료/실패 job 레코드 정리(메모리 바운드). 진행중 job 은 건드리지 않음."""
    now = time.time()
    stale = [
        jid
        for jid, j in _JOBS.items()
        if j["status"] in ("done", "error") and now - j["created"] > _JOB_TTL
    ]
    for jid in stale:
        _JOBS.pop(jid, None)


async def _run_synthesis_job(job_id: str, text: str, tone: str) -> None:
    """백그라운드 합성 워커 — GPU 직렬화(_gpu_sem) 하에 합성 후 결과를 _JOBS 에 기록.

    동기 /synthesize 와 같은 세마포어를 공유하므로 GPU 는 항상 한 번에 하나만 추론.
    """
    global _degraded
    async with _gpu_sem:  # GPU 한 번에 하나(동기 경로와 공유)
        try:
            result = await asyncio.wait_for(
                run_in_threadpool(synthesize, text, tone), timeout=_SYNTH_TIMEOUT
            )
            _JOBS[job_id].update(
                status="done",
                audio_path=result["audio_path"],
                duration=result["duration"],
                format=result["format"],
            )
        except asyncio.TimeoutError:  # 합성 hang(VRAM 고갈로 GPU 정체) — 스레드는 못 죽임
            _degraded = True  # qwen3 불가 표시 → 이후 폴백, 두 번째 생성 차단
            _JOBS[job_id].update(
                status="error", error="합성 시간 초과(GPU 정체) — 폴백 전환"
            )
        except ValueError as e:  # 빈 텍스트·미지원 보이스
            _JOBS[job_id].update(status="error", error=str(e))
        except Exception as e:  # noqa: BLE001 — 워커가 죽어도 서버는 살아야 함
            _JOBS[job_id].update(status="error", error=f"합성 실패: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """기동 시 모델 사전로드 → 첫 /synthesize 콜드스타트(~20s) 제거.

    부팅 직후 백엔드 첫 호출이 모델 로드를 기다리다 타임아웃→status=None 되던 문제 방지.
    블로킹 로드는 스레드풀에서 실행(이벤트 루프 안 막음). 로드 실패해도 서버는 떠서
    synthesize 의 lazy 로드로 폴백(헬스는 model_ready=False 로 표시).
    """
    global _model_ready
    try:
        await run_in_threadpool(_get_model)
        _model_ready = True
    except Exception as e:  # noqa: BLE001 — 기동 막지 않고 로그만, lazy 폴백
        print(f"[lifespan] 모델 사전로드 실패(lazy 폴백): {e}", file=sys.stderr)
    yield


app = FastAPI(title="Qwen3 TTS 추론 서비스", version="1.0", lifespan=lifespan)

# 라우터를 루트(/)와 /tts 두 곳에 마운트 → 백엔드 TTS_SERVER_URL 이
# 고정도메인 직결(루트)이든 프록시 경유(/tts)든 양쪽 다 응답.
# (ngrok 고정도메인을 8003 직결로 바꾸면 백엔드의 /tts/synthesize 가 404 나던 문제 방지.)
router = APIRouter()


class SynthesizeRequest(BaseModel):
    """백엔드 /tts 가 보내는 합성 요청 — tts.py/qwen3_synthesize 계약과 동일.

    백엔드가 보내는 키가 `tone` 또는 `voice` 양쪽으로 갈릴 수 있어(담당자별 변경)
    AliasChoices 로 둘 다 받는다 — 어느 키로 와도 안 깨짐. 값은 AVAILABLE_VOICES("boy"/"girl"/"woman").
    """

    text: str
    tone: str = Field(
        "girl", validation_alias=AliasChoices("tone", "voice")
    )


@router.get("/health")
def health() -> dict:
    """헬스 체크 — 터널·서비스 살아있는지 확인용 (모델 로드는 안 건드림)."""
    return {
        "status": "ok",
        "service": "qwen3-tts",
        "voices": list(AVAILABLE_VOICES),
        # _degraded(hang 감지) 시 false → 워치독·백엔드가 qwen3 대신 폴백 경로로.
        "model_ready": _model_ready and not _degraded,
        # 워치독이 콜드스타트(model_ready=false·degraded=false)와 hang(degraded=true)을
        # 구분해 hang 일 때만 자동 재시작하도록 명시 노출.
        "degraded": _degraded,
    }


@router.post("/synthesize")
async def synthesize_endpoint(req: SynthesizeRequest) -> FileResponse:
    """텍스트 -> 확정 보이스(boy/girl) 낭독 wav. 오디오 파일을 그대로 반환.

    duration/format 메타는 응답 헤더(X-Audio-Duration / X-Audio-Format)로 전달.
    """
    # 소형 대기큐: 슬롯이 차 있으면 즉시 503 대신 줄을 세운다(합성 ~10s 상한이라 안전).
    # 단 이미 _MAX_INFLIGHT 건이 처리/대기 중이면 과부하로 보고 즉시 503(백엔드 gTTS 폴백).
    global _inflight, _degraded
    if _degraded:  # hang 감지됨 — 새 생성 시작 금지(죽음의 소용돌이 방지). 백엔드는 폴백.
        raise HTTPException(status_code=503, detail="TTS 일시 불가(GPU 정체) — 폴백 사용")
    if _inflight >= _MAX_INFLIGHT:
        raise HTTPException(status_code=503, detail="TTS 서버 혼잡 — 잠시 후 재시도")
    _inflight += 1
    try:
        # GPU 슬롯을 기다린다. 제한시간 내 못 잡으면(앞이 너무 오래 걸림) 503.
        try:
            await asyncio.wait_for(_gpu_sem.acquire(), timeout=_ACQUIRE_TIMEOUT)
        except asyncio.TimeoutError:
            raise HTTPException(
                status_code=503, detail="TTS 대기 시간 초과 — 잠시 후 재시도"
            ) from None
        # 블로킹(GPU 추론) 호출 → 스레드풀에서 실행해 이벤트 루프 안 막음.
        try:
            result = await asyncio.wait_for(
                run_in_threadpool(synthesize, req.text, req.tone),
                timeout=_SYNTH_TIMEOUT,
            )
        except asyncio.TimeoutError:  # 합성 hang(GPU 정체) — 폴백 전환
            _degraded = True
            raise HTTPException(
                status_code=503, detail="합성 시간 초과(GPU 정체) — 폴백 사용"
            ) from None
        except ValueError as e:  # 빈 텍스트·미지원 보이스 → 400
            raise HTTPException(status_code=400, detail=str(e)) from e
        finally:
            _gpu_sem.release()
    finally:
        _inflight -= 1

    path = Path(result["audio_path"])
    return FileResponse(
        path=str(path),
        media_type="audio/wav",
        filename=path.name,
        headers={
            "X-Audio-Duration": str(result["duration"]),
            "X-Audio-Format": result["format"],
        },
    )


@router.post("/synthesize/async")
async def synthesize_async(req: SynthesizeRequest) -> dict:
    """비동기 합성 제출 — job_id 를 즉시 반환(합성은 백그라운드). 긴 메시지용.

    백엔드는 이 job_id 로 /synthesize/status 폴링 후 done 이면 /synthesize/result 다운로드.
    각 호출이 짧아 합성 길이·터널 타임아웃과 무관하게 안전하다.
    """
    if _degraded:  # hang 감지됨 — 새 생성 시작 금지(죽음의 소용돌이 방지). 백엔드는 폴백.
        raise HTTPException(status_code=503, detail="TTS 일시 불가(GPU 정체) — 폴백 사용")
    _purge_old_jobs()
    active = sum(1 for j in _JOBS.values() if j["status"] == "processing")
    if active >= _MAX_PENDING_JOBS:
        raise HTTPException(status_code=503, detail="TTS 서버 혼잡 — 잠시 후 재시도")
    job_id = uuid.uuid4().hex
    _JOBS[job_id] = {
        "status": "processing",
        "audio_path": None,
        "duration": None,
        "format": None,
        "error": None,
        "created": time.time(),
    }
    task = asyncio.create_task(_run_synthesis_job(job_id, req.text, req.tone))
    _BG_TASKS.add(task)  # 강참조 보관(GC 수거 방지)
    task.add_done_callback(_BG_TASKS.discard)  # 완료 시 자동 제거
    return {"job_id": job_id, "status": "processing"}


@router.get("/synthesize/status/{job_id}")
def synthesize_status(job_id: str) -> dict:
    """합성 진행 상태 조회 — processing/done/error."""
    job = _JOBS.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="알 수 없는 job_id")
    return {
        "status": job["status"],
        "duration": job["duration"],
        "format": job["format"],
        "error": job["error"],
    }


@router.get("/synthesize/result/{job_id}")
def synthesize_result(job_id: str) -> FileResponse:
    """완료된 합성 결과 wav 다운로드. 진행중=425, 실패=500, 없음=404."""
    job = _JOBS.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="알 수 없는 job_id")
    if job["status"] == "processing":
        raise HTTPException(status_code=425, detail="아직 합성 중 — 잠시 후 재시도")
    if job["status"] == "error":
        raise HTTPException(status_code=500, detail=job["error"] or "합성 실패")
    path = Path(job["audio_path"])
    return FileResponse(
        path=str(path),
        media_type="audio/wav",
        filename=path.name,
        headers={
            "X-Audio-Duration": str(job["duration"]),
            "X-Audio-Format": job["format"],
        },
    )


app.include_router(router)  # /health, /synthesize (고정도메인 8003 직결용)
app.include_router(router, prefix="/tts")  # /tts/health, /tts/synthesize (프록시/기존 .env 호환)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8002")))
