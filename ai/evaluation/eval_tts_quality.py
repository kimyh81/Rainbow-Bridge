"""TTS 음성 품질 평가 — CER/WER (Whisper STT + jiwer)

한국어는 조사/띄어쓰기 왜곡 때문에 CER가 주지표.
WER는 보조 참고용.

사전 설치:
    pip install openai-whisper jiwer

단일 파일 측정:
    python ai/evaluation/eval_tts_quality.py \\
        --audio path/to/tts.wav \\
        --text "원본 텍스트"

배치 측정 (JSON):
    python ai/evaluation/eval_tts_quality.py --batch samples.json
    # samples.json 형식: [{"audio": "a.wav", "text": "원문"}, ...]

결과 저장:
    python ai/evaluation/eval_tts_quality.py --audio a.wav --text "원문" --out result.json
"""

from __future__ import annotations

import argparse
import json
import os


def load_model(model_size: str = "large-v3"):
    try:
        import whisper
    except ImportError:
        raise SystemExit("openai-whisper 미설치 — pip install openai-whisper jiwer")
    print(f"[Whisper] 모델 로드 중: {model_size}")
    return whisper.load_model(model_size)


def speech_score(model, audio_path: str, original_text: str) -> dict:
    from jiwer import cer, wer

    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"오디오 파일 없음: {audio_path}")

    result = model.transcribe(audio_path, language="ko")
    heard = result["text"].strip()

    c = cer(original_text, heard)
    w = wer(original_text, heard)

    return {
        "audio": audio_path,
        "original": original_text,
        "recognized": heard,
        "CER": round(c, 4),   # 주지표 — 0에 가까울수록 발음 명확
        "WER": round(w, 4),   # 보조
        "pass": c < 0.10,     # CER 10% 미만 = 합격 기준 (팀 내부 기준)
    }


def print_result(r: dict) -> None:
    status = "✅ PASS" if r["pass"] else "❌ FAIL"
    print(f"\n{status}")
    print(f"  원문   : {r['original']}")
    print(f"  인식   : {r['recognized']}")
    print(f"  CER    : {r['CER']:.4f}  ({r['CER']*100:.1f}%)")
    print(f"  WER    : {r['WER']:.4f}  ({r['WER']*100:.1f}%)")


def run_batch(model, batch_path: str) -> list[dict]:
    with open(batch_path, encoding="utf-8") as f:
        samples = json.load(f)

    results = []
    for i, s in enumerate(samples, 1):
        print(f"\n[{i}/{len(samples)}] {s['audio']}")
        try:
            r = speech_score(model, s["audio"], s["text"])
            print_result(r)
            results.append(r)
        except Exception as e:
            print(f"  오류: {e}")
            results.append({"audio": s["audio"], "error": str(e)})

    passed = sum(1 for r in results if r.get("pass"))
    avg_cer = sum(r["CER"] for r in results if "CER" in r) / max(
        len([r for r in results if "CER" in r]), 1
    )
    print(f"\n── 배치 요약 ──────────────────────")
    print(f"  합계  : {len(results)}건  통과 {passed}건")
    print(f"  평균 CER: {avg_cer:.4f}  ({avg_cer*100:.1f}%)")
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="TTS CER/WER 평가")
    parser.add_argument("--audio", help="단일 오디오 파일 경로 (.wav/.mp3)")
    parser.add_argument("--text", help="원본 텍스트")
    parser.add_argument("--batch", help="배치 JSON 파일 경로")
    parser.add_argument("--model", default="large-v3", help="Whisper 모델 (기본: large-v3)")
    parser.add_argument("--out", help="결과 저장 JSON 경로 (선택)")
    args = parser.parse_args()

    if not args.audio and not args.batch:
        parser.print_help()
        return

    model = load_model(args.model)

    if args.batch:
        results = run_batch(model, args.batch)
    else:
        if not args.text:
            raise SystemExit("--text 옵션이 필요합니다")
        r = speech_score(model, args.audio, args.text)
        print_result(r)
        results = [r]

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"\n결과 저장: {args.out}")


if __name__ == "__main__":
    main()
