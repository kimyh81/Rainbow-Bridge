"""시연영상 대본 → Qwen3 음성 일괄 생성 (영상 더빙용).

scenario_lines.LINES 를 읽어 각 줄을 Qwen3 확정 보이스로 합성합니다.
결과 wav 는 ai/tts/_output/scenario/ 에 파일명대로 저장 → 영상 편집 때 얹으면 됩니다.
(백엔드·서버 캐시와 무관 — 순수 로컬 음성 생성)

긴 편지(특히 woman 화자)는 통째로 합성하면 후반 45초+ 발성 에너지가 죽는다
(측정 확인: 전체 RMS 0.106 대비 후반 0.003~0.008). 그래서 _SPLIT_NAMES 항목은
**문장 단위로 잘게(길이를 비슷하게)** 쪼개 합성한다.
  - 각 조각이 짧아 후반 음량 소실이 없다(끝까지 풀 음량).
  - 조각 길이가 비슷해 같은 seed 의 톤이 균질하다.
  - 조각별 RMS 를 중앙값으로 통일해 음량 변동을 없앤다.

실행 (전용 conda 환경에서, `-m` 금지 — __init__.py 가 google-cloud 끌어옴):
    conda run --no-capture-output -n qwen3-tts python ai/tts/synth_scenario.py

특정 줄만:
    conda run --no-capture-output -n qwen3-tts python ai/tts/synth_scenario.py --only letter_3rd

GPU 모델 첫 호출 때 로드(수십 초) 후 캐시. VRAM ~4.6GB — webui(8000) 동시 구동 금지.
"""

from __future__ import annotations

import os
import re
import sys

# qwen3_synthesize 가 import 시점에 _OUTPUT_DIR 을 고정하므로, import 전에 env 설정 필수.
_HERE = os.path.dirname(os.path.abspath(__file__))
_BASE = os.environ.get("TTS_OUTPUT_DIR") or os.path.join(_HERE, "_output")
os.environ["TTS_OUTPUT_DIR"] = os.path.join(_BASE, "scenario")

# __init__.py(google-cloud) 회피 — 같은 폴더 모듈 직접 import.
sys.path.insert(0, _HERE)
from qwen3_synthesize import synthesize  # noqa: E402
from scenario_lines import LINES  # noqa: E402

# 문장 단위 분할 합성을 적용할 파일명 (긴 편지의 후반 음량 소실 방지).
# ※ dynaudnorm 후처리 테스트 중 — 단일 합성 raw 가 필요해 비워 둠.
_SPLIT_NAMES: set[str] = set()
_CHUNK_MAX = 90    # 조각 최대 글자수 — 길면 후반 소실, 짧으면 톤 튐. 90 절충.
_GAP_SEC = 0.28    # 조각 사이 무음(초) — 자연스러운 문장 간격


def _chunk_text(text: str, max_len: int = _CHUNK_MAX) -> list[str]:
    """문장부호 기준으로 나눈 뒤, max_len 근처로 인접 문장을 합쳐 조각을 만든다.

    너무 짧은 조각(한두 단어)은 prosody 가 불안정하므로 붙이고,
    너무 긴 조각은 후반 소실이 나므로 끊는다 → 조각 길이를 고르게.
    """
    flat = " ".join(text.split())  # 줄바꿈·중복 공백 정리
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", flat) if s.strip()]
    chunks, cur = [], ""
    for s in sentences:
        if cur and len(cur) + 1 + len(s) > max_len:
            chunks.append(cur)
            cur = s
        else:
            cur = f"{cur} {s}".strip()
    if cur:
        chunks.append(cur)
    return chunks


def _synth_split(name: str, tone: str, text: str) -> dict:
    """문장 단위로 합성 → RMS 음량 통일 → 무음 끼워 이어붙이기."""
    import numpy as np
    import soundfile as sf

    parts = _chunk_text(text)
    out_dir = os.environ["TTS_OUTPUT_DIR"]

    audio, sr, tmp_paths = [], 24000, []
    for i, ct in enumerate(parts):
        r = synthesize(ct, tone, filename=f"{name}_p{i:02d}.wav")
        tmp_paths.append(r["audio_path"])
        data, sr = sf.read(r["audio_path"])
        audio.append(np.asarray(data, dtype=np.float64))

    # 조각별 음량(RMS) 을 중앙값으로 통일, 스케일업 클리핑만 방지.
    rmss = [float(np.sqrt(np.mean(c**2))) for c in audio]
    valid = [x for x in rmss if x > 0]
    target = float(np.median(valid)) if valid else 0.0
    norm = []
    for c, x in zip(audio, rmss):
        if target > 0 and x > 0:
            c = c * (target / x)
        peak = float(np.max(np.abs(c)))
        if peak > 0.97:
            c = c / peak * 0.97
        norm.append(c.astype(np.float32))

    gap = np.zeros(int(sr * _GAP_SEC), dtype=np.float32)
    merged = norm[0]
    for c in norm[1:]:
        merged = np.concatenate([merged, gap, c])

    final_path = os.path.join(out_dir, f"{name}.wav")
    sf.write(final_path, merged, sr)

    for p in tmp_paths:  # 조각 임시 wav 정리
        if os.path.exists(p):
            os.remove(p)

    return {
        "audio_path": final_path,
        "duration": round(len(merged) / sr, 1),
        "format": "wav",
        "chunks": len(parts),
    }


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser(description="시연영상 대본 → Qwen3 음성 일괄 생성")
    ap.add_argument("--only", default=None, help="해당 파일명 한 줄만 합성 (예: letter_3rd)")
    a = ap.parse_args()

    rows = [r for r in LINES if not a.only or r[0] == a.only]
    if not rows:
        print(f"일치 항목 없음: {a.only!r} — scenario_lines.LINES 의 파일명을 확인하세요.")
        return

    print(f"출력 폴더: {os.environ['TTS_OUTPUT_DIR']}")
    print(f"합성 대상: {len(rows)}줄\n")

    ok, fail = 0, 0
    for name, tone, text in rows:
        try:
            if name in _SPLIT_NAMES:
                r = _synth_split(name, tone, text)
                tag = f"OK·{r['chunks']}조각"
            else:
                r = synthesize(text, tone, filename=f"{name}.wav")
                tag = "OK"
            print(f"[{tag:9}] {name:16} {tone:6} {r['duration']:5.1f}s  {r['audio_path']}")
            ok += 1
        except Exception as exc:  # noqa: BLE001 — 한 줄 실패해도 나머지 계속
            print(f"[FAIL     ] {name:16} {tone:6} {exc}")
            fail += 1

    print(f"\n완료: 성공 {ok} / 실패 {fail}")


if __name__ == "__main__":
    main()
