"""④ TTS 서비스 — Qwen3 GPU 서버(B안) 또는 Google Cloud TTS 폴백.

구조(B안):
    프론트 → POST /tts (NCP 백엔드) → HTTP → 정환주 GPU 서버 /synthesize → Qwen3
TTS_SERVER_URL 미설정 시 Google TTS → gTTS 순으로 폴백.

⚠️ 윤리: 보호자 대상 낭독만. 반려동물 1인칭/목소리 흉내 ❌ (../CLAUDE.md §1).
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv
from google.auth.exceptions import DefaultCredentialsError

from app.schemas.tts import TtsCreate, TtsResponse
from app.db.redis_client import get_redis

logger = logging.getLogger(__name__)

# backend/app/services/tts.py → parents[3] = 레포 루트
_REPO_ROOT = Path(__file__).resolve().parents[3]

# 백엔드는 backend/ 에서 실행돼 루트 .env 를 자동 로드하지 않음 → 명시 로드.
load_dotenv(_REPO_ROOT / ".env")

# 인증 키 경로가 상대경로면 루트 기준 절대경로로 보정.
_cred = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
if _cred and not os.path.isabs(_cred):
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str((_REPO_ROOT / _cred).resolve())

# 합성 결과를 정적 서빙 폴더(main.py 의 /uploads 마운트)에 바로 저장.
os.environ.setdefault("TTS_OUTPUT_DIR", "uploads/tts")

# ai/tts import 하려면 레포 루트가 sys.path 에 있어야 함.
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# tone → Qwen3 보이스 키 매핑 (TtsTone 3종과 1:1)
# female: 1인칭 여성(girl) / male: 1인칭 남성(boy) / narration: 3인칭 나레이션(woman)
# ※ 메시지 톤(warm/calm/hopeful)과 TTS 톤은 별개 필드 — 프론트가 TTS 호출 시 직접 지정.
#   미지정·구버전 폴백은 narration(woman)이 기본.
_TONE_TO_VOICE: dict[str, str] = {
    "female": "girl",
    "male": "boy",
    "narration": "woman",
}
_DEFAULT_VOICE = "woman"  # 3인칭 나레이션이 기본 (TtsTone.NARRATION과 일치)


def _map_tone_to_voice(tone: str) -> str:
    """프론트 tone 값을 Qwen3 AVAILABLE_VOICES 키로 변환."""
    return _TONE_TO_VOICE.get(tone.lower(), _DEFAULT_VOICE)


async def generate_tts(data: TtsCreate) -> TtsResponse:
    """추모 메시지를 음성으로 합성해 재생용 URL 을 반환합니다.

    TTS_SERVER_URL 설정 시 Qwen3 GPU 서버(B안)로 호출.
    미설정 시 Google TTS → gTTS 순으로 폴백.
    TTS 완료 후 pet의 최신 무음 영상에 자동으로 음성을 합칩니다.
    """
    dyn = await get_redis().get("tts:server_url")
    tts_server_url = (dyn or os.environ.get("TTS_SERVER_URL", "")).strip()

    if tts_server_url:
        # 터널 끊김·타임아웃·5xx 등 remote 실패 시 500 대신 Google 폴백으로 자동 전환.
        try:
            result = await _qwen3_remote(data, tts_server_url)
        except (httpx.HTTPError, OSError) as exc:
            logger.warning(
                "Qwen3 remote TTS 실패(status=%s, detail=%s) → Google 폴백 사용",
                getattr(exc, "response", None) and exc.response.status_code,
                exc,
            )
            result = await _google_tts_fallback(data)
    else:
        result = await _google_tts_fallback(data)

    # TTS 완료 후 기존 영상에 자동으로 음성 합치기 (fire-and-forget, 실패해도 응답에 영향 없음)
    asyncio.create_task(
        _merge_tts_with_video(data.pet_id, result.audio_url.lstrip("/"))
    )
    return result


async def _qwen3_remote(data: TtsCreate, server_url: str) -> TtsResponse:
    """Qwen3 GPU 서버 비동기 잡 호출 — 제출→폴링→결과 다운로드.

    긴 메시지(70~210초 합성)가 단일 동기 호출의 60초 타임아웃을 넘겨 끊기던 문제를
    LivePortrait 와 동일한 비동기 잡 패턴으로 해결. 각 HTTP 호출이 짧아 안전.
    실패/타임아웃 시 httpx.HTTPError 를 올려 기존 Google 폴백 그대로 유지.
    """
    voice = _map_tone_to_voice(data.tone)
    filename = f"{data.pet_id}_{voice}_{abs(hash(data.text)) % 10_000_000}.wav"

    out_dir = Path(os.environ.get("TTS_OUTPUT_DIR", "uploads/tts"))
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / filename

    base = server_url.rstrip("/")
    async with httpx.AsyncClient(timeout=30.0) as client:
        # 1) 제출 → job_id 즉시 수신
        submit = await client.post(
            f"{base}/synthesize/async",
            json={"text": data.text, "voice": voice},
        )
        submit.raise_for_status()
        job_id = submit.json()["job_id"]

        # 2) 상태 폴링(3초 간격, 최대 ~360초) — 긴 메시지 합성시간 수용
        for _ in range(120):
            await asyncio.sleep(3)
            st = await client.get(f"{base}/synthesize/status/{job_id}")
            st.raise_for_status()
            status = st.json()["status"]
            if status == "done":
                break
            if status == "error":
                raise httpx.HTTPError(f"원격 합성 실패: {st.json().get('error')}")
        else:
            raise httpx.HTTPError("원격 합성 타임아웃(360s 초과)")

        # 3) 결과 wav 다운로드
        res = await client.get(f"{base}/synthesize/result/{job_id}")
        res.raise_for_status()
        out_path.write_bytes(res.content)
        duration = float(res.headers.get("X-Audio-Duration", 0))
        fmt = res.headers.get("X-Audio-Format", "wav")

    return TtsResponse(
        audio_url=f"/uploads/tts/{filename}",
        duration=duration,
        format=fmt,
    )


async def _google_tts_fallback(data: TtsCreate) -> TtsResponse:
    """TTS_SERVER_URL 미설정 시 Google TTS → gTTS 폴백."""
    filename = f"{data.pet_id}_{data.tone}_{abs(hash(data.text)) % 10_000_000}.mp3"
    try:
        from ai.tts import TtsTone, synthesize  # noqa: E402

        try:
            tone = TtsTone(data.tone)
        except ValueError:
            tone = TtsTone.NARRATION

        filename = f"{data.pet_id}_{tone.value}_{abs(hash(data.text)) % 10_000_000}.mp3"
        result = await asyncio.to_thread(synthesize, data.text, tone, filename=filename)
    except (ImportError, DefaultCredentialsError):
        logger.warning(
            "Google TTS 불가(ImportError 또는 GCP 인증 없음) → gTTS 폴백 사용"
        )
        result = await asyncio.to_thread(_gtts_fallback, data.text, filename)

    return TtsResponse(
        audio_url=f"/uploads/tts/{filename}",
        duration=result["duration"],
        format=result["format"],
    )


def _gtts_fallback(text: str, filename: str) -> dict:
    """GCP TTS 실패 시 gTTS로 대체 합성."""
    from gtts import gTTS

    out_dir = Path(os.environ.get("TTS_OUTPUT_DIR", "uploads/tts"))
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / filename
    gTTS(text=text, lang="ko").save(str(path))
    return {
        "audio_path": str(path),
        "duration": round(len(text) / 5.0, 1),
        "format": "mp3",
    }


async def _merge_tts_with_video(pet_id: str, tts_path: str) -> None:
    """TTS 완료 후 pet의 최신 영상에 음성을 자동으로 합칩니다 (fire-and-forget)."""
    try:
        from app.db.mongodb import mongodb

        doc = await mongodb.db["media_assets"].find_one(
            {"pet_id": pet_id, "status": "done", "video_url": {"$ne": None}},
            sort=[("created_at", -1)],
        )
        if not doc:
            return

        video_path = Path(doc["video_url"].lstrip("/"))
        if not video_path.exists():
            return

        tts_file = Path(tts_path)
        if not tts_file.exists():
            return

        out_dir = Path("uploads/videos")
        out_dir.mkdir(parents=True, exist_ok=True)
        output_path = out_dir / f"{video_path.stem}_voiced.mp4"

        if str(_REPO_ROOT) not in sys.path:
            sys.path.insert(0, str(_REPO_ROOT))

        from ai.liveportrait.pipeline import merge_audio

        voiced_path = await asyncio.to_thread(
            merge_audio, video_path, tts_file, output_path=output_path
        )
        await mongodb.db["media_assets"].update_one(
            {"_id": doc["_id"]},
            {"$set": {"voiced_url": f"/uploads/videos/{voiced_path.name}"}},
        )
        logger.info(
            "TTS→영상 자동 합치기 완료 pet_id=%s asset=%s", pet_id, str(doc["_id"])
        )
    except Exception:
        logger.warning("TTS→영상 자동 합치기 실패 pet_id=%s", pet_id, exc_info=True)
