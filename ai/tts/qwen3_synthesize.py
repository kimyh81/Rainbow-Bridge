"""④ TTS 합성 — Qwen3-TTS VoiceDesign 연동 (확정 보이스 3종).

tts.py(Google Cloud TTS)와 **같은 계약** `synthesize(text, tone)`을 Qwen3 로컬
GPU 엔진으로 제공합니다. 보이스는 정환주가 다이얼에서 고정한 **3종만** 노출:
  - "boy"   = Downloads/audio (10).wav  (PROTOTYPE_VOICE.md #3) — 1인칭 남성
  - "girl"  = Downloads/audio (6).wav   (PROTOTYPE_VOICE.md #4) — 1인칭 여성
  - "woman" = Downloads/audio (12).wav  (PROTOTYPE_VOICE.md #5) — 3인칭 나레이션
새 텍스트를 이 목소리(seed 고정)로 낭독합니다. 임의 화자 생성 아님.

윤리: 보호자 대상 위로 낭독만. 반려동물 목소리 흉내 ❌.

전용 conda 환경에서 실행/호출 (`-m` 금지 — __init__.py 가 google-cloud 끌어옴):
    conda run --no-capture-output -n qwen3-tts python ai/tts/qwen3_synthesize.py --tone girl
GPU 온디맨드(../tts/CLAUDE.md §4): 첫 호출 때 모델 로드(수십 초) 후 캐시.
VRAM ~4.6GB — webui(8000)와 동시 구동 시 8GB 초과 주의(하나만 띄울 것).
"""

from __future__ import annotations

import os
import sys

# anaconda libiomp5 중복 크래시 우회 (torch import 전).
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

# __init__.py(google-cloud) 회피 — 같은 폴더 모듈 직접 import.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from qwen3_emotion import _generate, _load_model, build_instruct  # noqa: E402
from tone_down import high_shelf  # noqa: E402  # 쨍함(고역) 톤다운, 다이얼과 동일

# 음성 파일 저장 위치 — git 미포함(.gitignore). tts.py 와 동일 env 키 사용.
# 기본값은 이 모듈 옆 _output(절대경로) — 자동기동 시 CWD 가 시스템 폴더라
# 상대경로("ai/tts/_output")면 거기에 폴더 생성이 WinError 5(권한 거부)로 실패함.
_OUTPUT_DIR = os.environ.get("TTS_OUTPUT_DIR") or os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "_output"
)

# 확정 보이스 3종 (PROTOTYPE_VOICE.md 동기화 — seed 가 화자 ID, 고정 필수).
_VOICES: dict[str, dict] = {
    # audio (10).wav — boy, 차분, 밝기 살짝 (#3)
    "boy": dict(
        gender="boy",
        age="older",
        warmth=1,
        bright=1,
        pitch="low",
        emotion="calm",
        clarity=0,
        pace="normal",
        temp=0.5,
        seed=29018,
        eq_db=9.0,
        eq_fc=7000.0,
        atempo=1.0,
    ),
    # audio (6).wav — girl, 차분 (#4)
    "girl": dict(
        gender="girl",
        age="older",
        warmth=0,
        bright=0,
        pitch="low",
        emotion="calm",
        clarity=0,
        pace="normal",
        temp=0.5,
        seed=46286,
        eq_db=9.0,
        eq_fc=4000.0,
        atempo=1.0,
    ),
    # woman, 성인 여성 차분 — 3인칭 나레이션 서비스 최종 보이스.
    # 다이얼은 audio12(PROTOTYPE_VOICE.md #5)와 동일(w1·b1·low·calm·c1·temp0.5·EQ미사용·seed21424).
    # 속도만 변경: pace slow→normal + atempo 0.9→0.95 (세종님 청취 후 확정 2026-06-11).
    "woman": dict(
        gender="woman",
        age="child",   # build_instruct에서 성인 앵커 사용 (age 무시됨)
        warmth=1,
        bright=1,
        pitch="low",
        emotion="calm",
        clarity=1,
        pace="normal",
        temp=0.5,
        seed=21424,
        eq_db=0.0,     # EQ 미사용
        eq_fc=4000.0,
        atempo=0.95,
    ),
}
# 호출부가 고를 수 있는 보이스 키(공개).
AVAILABLE_VOICES = tuple(_VOICES)

_model = None


def _apply_atempo(path: str, atempo: float) -> None:
    """ffmpeg atempo 필터로 속도 조정 (원본 덮어쓰기). ffmpeg 없으면 skip."""
    import shutil
    import subprocess

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg or atempo == 1.0:
        return
    tmp = path + ".atempo.wav"
    try:
        subprocess.run(
            [ffmpeg, "-y", "-i", path, "-filter:a", f"atempo={atempo}", tmp],
            check=True,
            capture_output=True,
            timeout=30,  # ffmpeg 멈춰도 합성 스레드 영구블록 방지 (woman 경로)
        )
        os.replace(tmp, path)
    except Exception:
        if os.path.exists(tmp):
            os.remove(tmp)


def _get_model():
    """온디맨드 단일 로드 — 첫 호출 때만 모델 적재(수십 초), 이후 재사용."""
    global _model
    if _model is None:
        _model = _load_model()
    return _model


def synthesize(text: str, tone: str = "girl", *, filename: str | None = None) -> dict:
    """텍스트를 확정 보이스로 합성해 wav 로 저장하고 메타데이터를 반환합니다.

    Args:
        text: 낭독할 보호자 대상 위로 메시지(반려동물 1인칭 ❌).
        tone: 보이스 키 — "boy"(audio10) / "girl"(audio6). (AVAILABLE_VOICES)
        filename: 저장 파일명(미지정 시 자동).

    Returns:
        {"audio_path": str, "duration": float, "format": "wav"}
        — 백엔드 MediaAsset 와 합의해 조정.

    Raises:
        ValueError: 빈 텍스트 또는 미지원 보이스 키.
    """
    import numpy as np
    import soundfile as sf
    import torch

    if not text or not text.strip():
        raise ValueError("합성할 텍스트가 비어 있습니다.")
    try:
        v = _VOICES[tone]
    except KeyError as e:
        raise ValueError(
            f"지원하지 않는 보이스: {tone!r}. 가능: {', '.join(_VOICES)}"
        ) from e

    instruct = build_instruct(
        v["gender"],
        v["warmth"],
        v["bright"],
        v["pace"],
        age=v["age"],
        pitch=v["pitch"],
        emotion=v["emotion"],
        clarity=v["clarity"],
    )
    model = _get_model()

    # seed 고정 — 같은 보이스(화자) 재현의 핵심.
    seed = v["seed"]
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)

    # max_new_tokens 상한 — codec EOS 미방출(반복루프)로 기본 8192 폭주 시 수백 초 hang 차단.
    # 3072 ≈ 255초·~1500자: 추모 메시지(600~800자) 안 자름, 폭주(8192)만 차단.
    out = _generate(
        model, text, instruct, {"temperature": v["temp"], "max_new_tokens": 3072}
    )
    wavs, sr = out if isinstance(out, tuple) else (out, 24000)
    wav = wavs[0] if hasattr(wavs, "__len__") and not hasattr(wavs, "ndim") else wavs
    wav = np.asarray(wav, dtype=np.float32)

    peak = float(np.max(np.abs(wav)))
    if peak > 0:  # 목소리 작음 보정 (약 -0.5dBFS)
        wav = wav / peak * 0.95
    if v["eq_db"] > 0:  # 쨍함(날카로운 고역) 톤다운 — 다이얼과 동일 high-shelf 감쇠
        wav = high_shelf(wav, sr, v["eq_fc"], -v["eq_db"]).astype(np.float32)

    os.makedirs(_OUTPUT_DIR, exist_ok=True)
    name = filename or f"qwen3tts_{tone}_{abs(hash(text)) % 10_000_000}.wav"
    path = os.path.join(_OUTPUT_DIR, name)
    sf.write(path, wav, sr)
    if v.get("atempo", 1.0) != 1.0:
        _apply_atempo(path, v["atempo"])

    # 매 합성 후 CUDA 캐시 반납 — 요청 간 VRAM 누적/단편화 방지 (8GB 공유 환경).
    torch.cuda.empty_cache()
    return {"audio_path": path, "duration": round(len(wav) / sr, 1), "format": "wav"}


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="Qwen3 확정 보이스 합성 (boy/girl)")
    ap.add_argument("--tone", choices=list(_VOICES), default="girl")
    ap.add_argument(
        "--text",
        default="오늘 하루도 정말 수고 많으셨어요. 천천히, 편안하게 쉬어도 괜찮아요.",
    )
    ap.add_argument("--out", default=None, help="저장 파일명(미지정 시 자동)")
    a = ap.parse_args()
    print(synthesize(a.text, a.tone, filename=a.out))
