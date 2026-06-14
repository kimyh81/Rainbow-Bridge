"""④ TTS 서비스 — Qwen3 GPU 서버(B안) → WaveSpeedAI → Google Cloud TTS 폴백.

구조:
    프론트 → POST /tts (NCP 백엔드) → HTTP → 정환주 GPU 서버 /synthesize → Qwen3
    GPU 서버 실패 시: WAVESPEED_API_KEY 있으면 WaveSpeedAI(Qwen3 동일 모델) → Google TTS → gTTS

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

# WaveSpeedAI 음성 매핑 + style_instruction (voice_key × species 조합 감성 프롬프트)
_WAVESPEED_VOICE_MAP: dict[str, str] = {
    "girl": "Vivian",
    "boy": "Eric",
    "woman": "Vivian",
}
_WAVESPEED_STYLE: dict[str, dict[str, str]] = {
    "girl": {
        "강아지": (
            "A soft, gentle voice of a young girl around 8-10 years old, speaking in Korean. "
            "Warm, bright, and deeply loyal — like a beloved dog saying goodbye with a wagging heart. "
            "Pure unconditional love in every word. Slow and heartfelt, "
            "slightly emotional but ultimately comforting and cheerful. Clear and airy tone."
        ),
        "고양이": (
            "A soft, gentle voice of a young girl around 8-10 years old, speaking in Korean. "
            "Quiet, graceful, and deeply tender — like a beloved cat expressing its hidden affection for the last time. "
            "Warm beneath the calm. Slow and deliberate, "
            "slightly melancholic but ultimately peaceful. Clear and silky tone."
        ),
        "기타": (
            "A soft, gentle voice of a young girl around 8-10 years old, speaking in Korean. "
            "Warm, tender, and deeply loving — like a beloved pet saying a final farewell. "
            "Slow and heartfelt, slightly emotional but ultimately comforting. Clear and airy tone."
        ),
    },
    "boy": {
        "강아지": (
            "A soft, gentle voice of a young boy around 8-10 years old, speaking in Korean. "
            "Sincere, brave, and unconditionally loyal — like a cherished dog expressing deepest love before parting. "
            "Energetic spirit softened by emotion, melancholic but reassuring. "
            "Slow and deliberate with quiet strength. Clear and pure tone."
        ),
        "고양이": (
            "A soft, gentle voice of a young boy around 8-10 years old, speaking in Korean. "
            "Quiet, dignified, and deeply affectionate — like a beloved cat who rarely showed love but felt it completely. "
            "Reserved yet sincere, with subtle warmth in every pause. Slow and thoughtful, "
            "melancholic but serene. Clear and calm tone."
        ),
        "기타": (
            "A soft, gentle voice of a young boy around 8-10 years old, speaking in Korean. "
            "Sincere, warm, and quietly brave — like a cherished pet expressing its deepest love before parting. "
            "Slow and deliberate, melancholic but reassuring. Clear and pure tone."
        ),
    },
    "woman": {
        "강아지": (
            "A warm, calm adult female voice speaking Korean, like a trusted friend offering comfort during grief. "
            "Soft and deeply empathetic, carrying the spirit of a loyal dog's unconditional love. "
            "Slow with gentle pauses. Compassionate, grounded, and healing."
        ),
        "고양이": (
            "A warm, calm adult female voice speaking Korean, like a trusted friend offering comfort during grief. "
            "Soft and deeply empathetic, carrying the quiet elegance of a cat's mysterious affection. "
            "Slow with gentle pauses. Compassionate, grounded, and healing."
        ),
        "기타": (
            "A warm, calm adult female voice speaking Korean, like a trusted friend offering comfort during grief. "
            "Soft and deeply empathetic. Slow with gentle pauses. "
            "Like a quiet hand on the shoulder — compassionate, grounded, and healing."
        ),
    },
}


def _map_tone_to_voice(tone: str) -> str:
    """프론트 tone 값을 Qwen3 AVAILABLE_VOICES 키로 변환."""
    return _TONE_TO_VOICE.get(tone.lower(), _DEFAULT_VOICE)


async def generate_tts(data: TtsCreate) -> TtsResponse:
    """추모 메시지를 음성으로 합성해 재생용 URL 을 반환합니다.

    TTS_SERVER_URL 설정 시 Qwen3 GPU 서버(B안)로 호출.
    미설정 시 Google TTS → gTTS 순으로 폴백.
    TTS 완료 후 pet의 최신 무음 영상에 자동으로 음성을 합칩니다.

    동일 (pet_id, text, tone) 조합은 기존 파일을 재사용합니다 (idempotent).
    """
    voice_key = _map_tone_to_voice(data.tone)
    text_hash = abs(hash(data.text)) % 10_000_000
    out_dir = Path(os.environ.get("TTS_OUTPUT_DIR", "uploads/tts"))
    # qwen3/wavespeed 파일명: {voice_key}, google fallback 파일명: {tone} — 둘 다 체크.
    for stem in (
        f"{data.pet_id}_{voice_key}_{text_hash}",
        f"{data.pet_id}_{data.tone}_{text_hash}",
    ):
        for ext in ("mp3", "wav"):
            cached = out_dir / f"{stem}.{ext}"
            if cached.exists():
                logger.info("TTS 캐시 hit: %s", cached.name)
                return TtsResponse(
                    audio_url=f"/uploads/tts/{cached.name}", duration=0, format=ext
                )

    dyn = await get_redis().get("tts:server_url")
    tts_server_url = (dyn or os.environ.get("TTS_SERVER_URL", "")).strip()

    wavespeed_key = os.environ.get("WAVESPEED_API_KEY", "").strip()

    if tts_server_url:
        # 터널 끊김·타임아웃·5xx 등 remote 실패 시 WaveSpeedAI → Google 순으로 폴백.
        try:
            result = await _qwen3_remote(data, tts_server_url)
        except (httpx.HTTPError, OSError) as exc:
            logger.warning(
                "Qwen3 remote TTS 실패(status=%s, detail=%s) → WaveSpeedAI/Google 폴백",
                getattr(exc, "response", None) and exc.response.status_code,
                exc,
            )
            result = await _wavespeed_or_google(data, wavespeed_key)
    elif wavespeed_key:
        result = await _wavespeed_tts(data, wavespeed_key)
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


async def _wavespeed_or_google(data: TtsCreate, wavespeed_key: str) -> TtsResponse:
    """WaveSpeedAI 시도 → 실패 시 Google 폴백."""
    if wavespeed_key:
        try:
            return await _wavespeed_tts(data, wavespeed_key)
        except Exception as exc:
            logger.warning("WaveSpeedAI TTS 실패(%s) → Google 폴백", exc)
    return await _google_tts_fallback(data)


async def _wavespeed_tts(data: TtsCreate, api_key: str) -> TtsResponse:
    """WaveSpeedAI Qwen3 TTS API 호출 (로컬 GPU 대체, 동일 모델).

    엔드포인트: POST /api/v3/wavespeed-ai/qwen3-tts/text-to-speech
    응답: data.id → 폴링 → data.outputs[0] (오디오 URL)
    style_instruction으로 tone별 감성 프롬프트 전달.
    """
    voice_key = _map_tone_to_voice(data.tone)
    ws_voice = _WAVESPEED_VOICE_MAP.get(voice_key, "Vivian")
    species = (
        (data.species or "강아지")
        if data.species in ("강아지", "고양이", "기타")
        else "기타"
    )
    style = _WAVESPEED_STYLE.get(voice_key, _WAVESPEED_STYLE["woman"]).get(
        species, _WAVESPEED_STYLE["woman"]["기타"]
    )
    filename = f"{data.pet_id}_{voice_key}_{abs(hash(data.text)) % 10_000_000}.mp3"
    out_dir = Path(os.environ.get("TTS_OUTPUT_DIR", "uploads/tts"))
    out_dir.mkdir(parents=True, exist_ok=True)

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30.0) as client:
        # 1) 제출
        submit = await client.post(
            "https://api.wavespeed.ai/api/v3/wavespeed-ai/qwen3-tts/text-to-speech",
            headers=headers,
            json={
                "text": data.text,
                "voice": ws_voice,
                "language": "auto",
                "style_instruction": style,
            },
        )
        submit.raise_for_status()
        resp_data = submit.json()["data"]
        poll_url = resp_data["urls"]["get"]

        # 2) 폴링 (3초 간격, 최대 5분)
        for _ in range(100):
            await asyncio.sleep(3)
            status_res = await client.get(poll_url, headers=headers)
            status_res.raise_for_status()
            body = status_res.json()["data"]
            if body["status"] == "completed":
                audio_url = body["outputs"][0]
                break
            if body["status"] == "failed":
                raise httpx.HTTPError(f"WaveSpeed 합성 실패: {body.get('error')}")
        else:
            raise httpx.HTTPError("WaveSpeed 폴링 타임아웃(5분)")

        # 3) 오디오 다운로드
        audio_res = await client.get(audio_url)
        audio_res.raise_for_status()
        (out_dir / filename).write_bytes(audio_res.content)

    logger.info("WaveSpeedAI TTS 완료: %s (%s)", filename, ws_voice)
    return TtsResponse(audio_url=f"/uploads/tts/{filename}", duration=0, format="mp3")


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
