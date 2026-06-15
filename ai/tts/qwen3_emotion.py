"""Qwen3-TTS VoiceDesign — '어린아이 음색 + 감정'을 한 instruct에 동시 주입 (스파이크).

배경: 서비스에 어린아이 톤 + 감정(슬픔·위로)이 담긴 추모 낭독 목소리가 필요.
이전 qwen3_design.py 는 음색(어린아이)만 줘서 "별로" 판정 → 이번엔
instruct 에 **나이(어린아이) + 감정(슬픔·그리움·위로)** 을 동시에 묘사해 추모 낭독 톤을 뽑는다.

윤리: 텍스트는 보호자 대상 위로 멘트(1인칭/특정 반려동물 ❌) 그대로 — 음색·감정만 평가.
(반려동물 1인칭 작별 화법은 동의+경고+risk0~1 조건부라, 톤 탐색 단계에선 중립 멘트로.)

전용 conda 환경에서 파일 직접 실행 (`-m` 금지 — ai/tts/__init__.py 가 google-cloud 끌어옴):
    conda run --no-capture-output -n qwen3-tts python ai/tts/qwen3_emotion.py
출력:
    ai/tts/_output/qwen3_emotion/qwen3em_{라벨}.wav  → 어린아이+감정 청취.
"""

from __future__ import annotations

import os
import sys

# anaconda libiomp5 중복 크래시 우회 (torch import 전).
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

_OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_output", "qwen3_emotion")
_MODEL_ID = "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign"

# 다른 엔진 스파이크와 동일 텍스트(공정 비교) — 보호자 위로 멘트.
# boy_warm(호흡 없는 원본 텍스트)이 베스트 판정 → 원본 복귀(과한 호흡이 쳐짐 유발).
_TEXT = (
    "오늘도 마음이 많이 무거우셨죠. 함께한 시간들은 사라지지 않고 "
    "당신 곁에 따뜻하게 남아 있어요. 너무 자책하지 마시고, "
    "천천히 호흡하며 오늘 하루를 보내셔도 괜찮아요."
)

# boy 집중 — 직전 boy_warm 류 "너무 느끼함 + 귀에 속삭임" 판정.
# 원인 = soft/warm-loving/gently/bittersweet/soothing 누적 → 과한 감정(느끼) +
# 친밀·숨소리(속삭임). 정규화로 볼륨만 키우니 속삭임이 더 도드라짐.
# 방향 전환: 또렷·담백·정직한 또래 아이, 보통 거리에서 말하듯, 감정 절제.
# soft/whisper/breathy/loving/soothing/bittersweet 제거 → clear/plain/sincere/
# normal distance/not whispering. 튜플 = (라벨, instruct, gen_kwargs)
# v5(담백)도 느끼/속삭임 잔존 판정. instruct 의 감정어("restrained emotion")조차
# 느끼함을 재유입 + child+gentle 조합이 숨소리 친밀 톤으로 기우는 모델 성향.
# → 감정어 0, 낭독·투사 레지스터로 전환: matter-of-fact / reading aloud /
#   full voice projecting / not intimate. seed 변주 + 낮은 temp 로 덜 느끼한 take 선택.
_BOY_READ_BASE = (
    "A little Korean boy reading a message aloud clearly and plainly, "
    "matter-of-fact and calm, full and present voice projected at a normal distance, "
    "even pace, not intimate, not soft, not breathy, not whispering, no exaggerated emotion"
)
_DESIGNS: tuple[tuple[str, str, dict], ...] = (
    # v9: 낭독·투사 베이스 (감정어 0) — 느끼/속삭임 차단 기준
    ("boy_read_v9", _BOY_READ_BASE, {"temperature": 0.7, "seed": 7}),
    # v10: 같은 instruct 다른 seed (덜 느끼한 take 비교)
    ("boy_read_v10", _BOY_READ_BASE, {"temperature": 0.7, "seed": 19}),
    # v11: 더 단단하게 + temp 더 낮춤 (떨림·느끼 억제 최대)
    (
        "boy_read_v11_firm",
        _BOY_READ_BASE + ", firm, grounded and steady",
        {"temperature": 0.6, "seed": 31},
    ),
    # v12: 또박또박 또렷 강조 (속삭임 반대편 — 발음 분명)
    (
        "boy_read_v12_artic",
        _BOY_READ_BASE + ", articulate and crisp pronunciation",
        {"temperature": 0.65, "seed": 43},
    ),
)

# girl 재합성 v2 — 억양이 괜찮은 boy_read 레시피를 girl 로 그대로 치환(감정어 0,
# 낭독·투사 레지스터). 옛 감정어(soft/warm-loving/gently/bittersweet/soothing)가
# boy 에서 억양 어색·느끼·쨍함 유발한 그 방향이라 girl 에서도 동일 실패 → 제거.
# boy 와 같은 seed/temp(7/19/31/43) 사용 — 억양 검증된 조건 그대로 옮김.
_GIRL_READ_BASE = (
    "A little Korean girl reading a message aloud clearly and plainly, "
    "matter-of-fact and calm, full and present voice projected at a normal distance, "
    "even pace, not intimate, not soft, not breathy, not whispering, no exaggerated emotion"
)
_GIRL_DESIGNS: tuple[tuple[str, str, dict], ...] = (
    # boy_read base 그대로 (seed 7,19) — 억양 검증 조건
    ("girl_read_v9", _GIRL_READ_BASE, {"temperature": 0.7, "seed": 7}),
    ("girl_read_v10", _GIRL_READ_BASE, {"temperature": 0.7, "seed": 19}),
    # 단단·안정 (낮은 temp)
    ("girl_read_v11_firm", _GIRL_READ_BASE + ", firm, grounded and steady", {"temperature": 0.6, "seed": 31}),
    # 쩅함 대비 — 감정어는 0 유지, 고역만 억제
    ("girl_read_v12_mellow", _GIRL_READ_BASE + ", warm and mellow, not bright or sharp", {"temperature": 0.65, "seed": 43}),
)


def _load_model():
    import torch
    from qwen_tts import Qwen3TTSModel

    if not torch.cuda.is_available():
        print("[warn] CUDA 사용 불가 → CPU 추론(느림). torch cu128 설치 확인 필요.")
        device, dtype, attn = "cpu", torch.float32, None
    else:
        print(f"[gpu] {torch.cuda.get_device_name(0)}")
        device, dtype, attn = "cuda:0", torch.float16, None

    kwargs = dict(device_map=device, dtype=dtype)
    if attn:
        kwargs["attn_implementation"] = attn
    return Qwen3TTSModel.from_pretrained(_MODEL_ID, **kwargs)


# 외부 튜닝법 중 Qwen3 에 실제 적용 가능한 레버만 채택:
#  - temperature 낮춤(감정 변동↓·안정) — _merge_generate_kwargs 가 kwargs 로 받음
#  - instruct 톤다운 문구(낮고 부드러운 피치·차분·과한 밝기 제거)
#  - 텍스트 호흡(쉼표·말줄임)은 _TEXT 에 반영
# (stability·speed_rate·style_overlap 은 Qwen3 에 없음 → ElevenLabs 개념이라 미적용)
_TEMP = 0.7
_CALM_SUFFIX = " Low and soft pitch, calm and quiet, gently emotional with no brightness."


def _generate(model, text: str, instruct: str, gen_kwargs: dict | None = None):
    """VoiceDesign 합성. 패키지 버전별 메서드명 차이 방어. language 는 소문자 'korean'."""
    gen_kwargs = gen_kwargs or {}
    last_exc = None
    for method in ("generate_voice_design", "generate_custom_voice"):
        fn = getattr(model, method, None)
        if fn is None:
            continue
        for kw in (
            dict(text=text, language="korean", instruct=instruct, **gen_kwargs),
            dict(text=text, language="korean", speaker="default", instruct=instruct, **gen_kwargs),
        ):
            try:
                return fn(**kw)
            except TypeError as e:
                last_exc = e
                continue
    raise RuntimeError(f"VoiceDesign 호출 실패(메서드/시그니처 불일치): {last_exc}")


# ── 다이얼(감도 조절) ──────────────────────────────────────────────
# 사용자가 직접 노브를 돌려 합성. 아이 앵커는 항상 강하게 고정(아저씨 목소리 방지).
# 단계 숫자가 클수록 강함. instruct 문구만 바뀌고 temperature/seed 는 별도 인자.
_CHILD_ANCHOR = (
    "A young Korean {g}, a small child {age}, with a clearly childlike high and light voice"
)
_AGE = {  # 어릴수록 톤 높고 가벼움
    "younger": "about five years old",
    "child": "about seven years old",
    "older": "about ten years old",
}
_WARMTH = {  # 느끼(다정) 강도
    0: ", plain and matter-of-fact",
    1: ", calm and sincere",
    2: ", gently warm",
    3: ", warm and tender",
}
_BRIGHT = {  # 밝기(쳐짐 반대)
    0: ", low and subdued tone",
    1: ", natural tone",
    2: ", clear and bright",
    3: ", bright and lively",
}
_PITCH = {"low": ", with a lower pitch", "normal": "", "high": ", with a higher pitch"}
_EMOTION = {  # 감정 결 (없음=중립)
    "none": "",
    "calm": ", calm and composed",
    "sad": ", with quiet gentle sadness",
    "comfort": ", comforting and reassuring",
}
_CLARITY = {  # 또렷함(속삭임 반대)
    0: "",
    1: ", articulate",
    2: ", articulate with crisp clear pronunciation",
}
_PACE = {
    "slow": ", speaking slowly",
    "normal": ", speaking at a natural pace",
    "fast": ", speaking a bit faster",
}
# 항상 붙는 꼬리 — 속삭임/숨소리/성인 톤 차단 (어린이용)
_TAIL = ", speaking out loud at a normal distance, not whispering, not breathy, clearly a child and not an adult"

# 성인 앵커 — 3인칭 추모 낭독용(메시지 읽어주기). g = man / woman.
_ADULT_ANCHOR = "A Korean adult {g}, with a clear, natural, mature voice"
# 성인 꼬리 — 속삭임/숨소리만 차단(어린이 단정 문구 제외).
_ADULT_TAIL = ", speaking out loud at a normal distance, not whispering, not breathy"


def build_instruct(
    gender: str,
    warmth: int,
    bright: int,
    pace: str,
    age: str = "child",
    pitch: str = "normal",
    emotion: str = "none",
    clarity: int = 0,
) -> str:
    if gender in ("man", "woman"):  # 성인 — age 무시, 성인 앵커/꼬리 사용
        anchor = _ADULT_ANCHOR.format(g=gender)
        tail = _ADULT_TAIL
    else:  # 어린이 — boy/girl
        g = "boy" if gender == "boy" else "girl"
        anchor = _CHILD_ANCHOR.format(g=g, age=_AGE[age])
        tail = _TAIL
    return (
        anchor
        + _WARMTH[warmth]
        + _BRIGHT[bright]
        + _PITCH[pitch]
        + _EMOTION[emotion]
        + _CLARITY[clarity]
        + _PACE[pace]
        + tail
    )


def main() -> None:
    import argparse
    import time

    import numpy as np
    import soundfile as sf
    import torch

    ap = argparse.ArgumentParser(description="Qwen3 어린아이 목소리 감도 조절 합성")
    ap.add_argument("--batch", choices=["boy", "girl"], help="기존 배치(다이얼 무시)")
    ap.add_argument("--gender", choices=["boy", "girl", "man", "woman"], default="boy")
    ap.add_argument("--warmth", type=int, choices=[0, 1, 2, 3], default=1, help="다정/느끼 강도")
    ap.add_argument("--bright", type=int, choices=[0, 1, 2, 3], default=1, help="밝기(쳐짐 반대)")
    ap.add_argument("--pace", choices=["slow", "normal"], default="normal")
    ap.add_argument("--temp", type=float, default=0.8, help="안정성(낮을수록 흔들림↓)")
    ap.add_argument("--seed", type=int, default=7, help="같은 설정 다른 take")
    ap.add_argument("--text", default=_TEXT)
    ap.add_argument("--label", default=None)
    args = ap.parse_args()

    if args.batch:
        designs = _GIRL_DESIGNS if args.batch == "girl" else _DESIGNS
        text = _TEXT
        head = f"{args.batch} 배치 ({len(designs)}종)"
    else:
        instruct = build_instruct(args.gender, args.warmth, args.bright, args.pace)
        label = args.label or (
            f"dial_{args.gender}_w{args.warmth}_b{args.bright}_{args.pace}"
            f"_t{args.temp}_s{args.seed}"
        )
        designs = ((label, instruct, {"temperature": args.temp, "seed": args.seed}),)
        text = args.text
        head = f"다이얼 {args.gender} | warmth {args.warmth} bright {args.bright} " \
               f"{args.pace} temp {args.temp} seed {args.seed}"

    os.makedirs(_OUT_DIR, exist_ok=True)
    print(f"== Qwen3-TTS 어린아이 합성 → {_OUT_DIR} ==")
    print(f"대상: {head}")
    if not args.batch:
        print(f"instruct: {designs[0][1]}")
    print(f"텍스트({len(text)}자): {text}\n")
    model = _load_model()
    cuda = torch.cuda.is_available()

    tot_infer = 0.0
    tot_audio = 0.0
    n = 0
    for label, instruct, gk in designs:
        dest = os.path.join(_OUT_DIR, f"qwen3em_{label}.wav")
        try:
            gk = dict(gk)
            seed = gk.pop("seed", None)
            if seed is not None:  # 같은 instruct 라도 억양 변동 다양화
                torch.manual_seed(seed)
                if cuda:
                    torch.cuda.manual_seed_all(seed)
            if cuda:
                torch.cuda.reset_peak_memory_stats()
            t0 = time.perf_counter()
            out = _generate(model, text, instruct, gk)
            dt = time.perf_counter() - t0

            wavs, sr = out if isinstance(out, tuple) else (out, 24000)
            wav = wavs[0] if hasattr(wavs, "__len__") and not hasattr(wavs, "ndim") else wavs
            # 목소리 작음 보정 — peak 정규화(약 -0.5dBFS)
            peak = float(np.max(np.abs(wav)))
            if peak > 0:
                wav = wav / peak * 0.95
            sf.write(dest, wav, sr)

            dur = len(wav) / sr
            rtf = dt / dur if dur else 0.0
            vram = torch.cuda.max_memory_allocated() / 1e9 if cuda else 0.0
            tot_infer += dt
            tot_audio += dur
            n += 1
            print(
                f"saved qwen3em_{label}.wav | 추론 {dt:.1f}s | 오디오 {dur:.1f}s | "
                f"RTF {rtf:.2f} | VRAM peak {vram:.1f}GB"
            )
        except Exception as e:
            print(f"[fail] {label}: {type(e).__name__}: {str(e)[:200]}")

    if n:
        avg_rtf = tot_infer / tot_audio if tot_audio else 0.0
        print(
            f"\n[누적] {n}건 | 총 추론 {tot_infer:.1f}s | 총 오디오 {tot_audio:.1f}s | "
            f"평균 RTF {avg_rtf:.2f}"
        )
    print("done — _output/qwen3_emotion/ 청취 (어린아이+감정 조합 비교)")


if __name__ == "__main__":
    main()
