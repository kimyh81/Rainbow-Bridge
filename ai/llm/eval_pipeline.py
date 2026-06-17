"""§ 0 검문소 파이프라인 — 텍스트·음성·영상·시스템 점수를 하나로 모아 최종 평가표 생성.

검문소별 구현 위치:
  A. G-Eval (대화 품질)    → ai/llm/g_eval.py            담당: 반소람  ✅
  B. CER/WER (음성 품질)   → ai/tts/analyze_stt.py       담당: 정환주님 ✅ (일부)
  C. SyncNet (립싱크)      → ai/liveportrait/ (예정)      담당: 장민수님 ⬜
  D. TTFB/FPS/완료율       → backend/ (예정)              담당: 세종/윤한님, 민경이님 ⬜

사용법:
  # 1단계: G-Eval 먼저 돌리기
  python -m ai.llm.g_eval --out geval_results.json

  # 2단계: 파이프라인에서 취합 (없는 검문소는 자동 스킵)
  python -m ai.llm.eval_pipeline --geval geval_results.json
  python -m ai.llm.eval_pipeline --geval geval_results.json --cer cer_results.json
  python -m ai.llm.eval_pipeline --geval geval_results.json --cer cer.json --syncnet lse.json --system system_metrics.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from statistics import mean
from typing import Any

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

# ────────────────────────────────────────────────────────────────
# 각 검문소 결과 로더
# ────────────────────────────────────────────────────────────────

def _load_geval(path: Path) -> dict[str, float]:
    """g_eval.py 출력 JSON → 지표 평균 dict.

    반환: {"consistency": 4.2, "usefulness": 3.6, "naturalness": 4.0, "ethics": 4.8}
    """
    with open(path, encoding="utf-8") as f:
        results = json.load(f)

    scored = [r for r in results if "scores" in r]
    if not scored:
        return {}

    all_keys = {k for r in scored for k in r["scores"]}
    return {
        k: round(mean(r["scores"][k] for r in scored if k in r["scores"]), 2)
        for k in all_keys
    }


def _load_cer(path: Path) -> dict[str, float]:
    """CER 결과 JSON → 지표 dict.

    정환주님 analyze_stt.py 결과를 아래 형식으로 저장해서 넘겨주시면 됩니다:
    {"cer": 0.06, "wer": 0.12}   (값이 낮을수록 좋음)
    """
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return {
        "CER": data.get("cer", data.get("CER", None)),
        "WER": data.get("wer", data.get("WER", None)),
    }


def _load_syncnet(path: Path) -> dict[str, float]:
    """SyncNet 결과 JSON → 지표 dict.

    장민수님 SyncNet 실행 후 아래 형식으로 저장해서 넘겨주시면 됩니다:
    {"lse_c": 6.8, "lse_d": 7.1}
    LSE-C 높을수록 좋음 / LSE-D 낮을수록 좋음
    """
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return {
        "LSE-C": data.get("lse_c", data.get("LSE-C", None)),
        "LSE-D": data.get("lse_d", data.get("LSE-D", None)),
    }


def _load_system_metrics(path: Path) -> dict[str, float]:
    """시스템 지표 JSON → 지표 dict.

    세종/윤한님(TTFB·완료율), 민경이님(FPS) 결과를 아래 형식으로 저장해서 넘겨주시면 됩니다:
    {"ttfb": 1.3, "fps": 30, "completion_rate": 82}
    """
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return {
        "TTFB(초)":    data.get("ttfb", data.get("TTFB", None)),
        "FPS":         data.get("fps",  data.get("FPS",  None)),
        "완료율(%)":   data.get("completion_rate", data.get("완료율", None)),
    }


# ────────────────────────────────────────────────────────────────
# 목표 기준
# ────────────────────────────────────────────────────────────────

_GOALS: dict[str, Any] = {
    "consistency":  ("≥ 4.0", lambda v: v >= 4.0),
    "usefulness":   ("≥ 4.0", lambda v: v >= 4.0),
    "naturalness":  ("≥ 4.0", lambda v: v >= 4.0),
    "ethics":       ("≥ 4.0", lambda v: v >= 4.0),
    "CER":          ("≤ 0.10", lambda v: v <= 0.10),
    "WER":          ("≤ 0.20", lambda v: v <= 0.20),
    "LSE-C":        ("≥ 6.0",  lambda v: v >= 6.0),
    "LSE-D":        ("낮을수록", lambda v: True),
    "TTFB(초)":    ("≤ 1.5",  lambda v: v <= 1.5),
    "FPS":          ("≥ 30",   lambda v: v >= 30),
    "완료율(%)":   ("≥ 80",   lambda v: v >= 80),
}

_LAYER_MAP: dict[str, str] = {
    "consistency": "대화 (검문소 A)",
    "usefulness":  "대화 (검문소 A)",
    "naturalness": "대화 (검문소 A)",
    "ethics":      "대화 (검문소 A)",
    "CER":         "음성 (검문소 B)",
    "WER":         "음성 (검문소 B)",
    "LSE-C":       "영상 (검문소 C)",
    "LSE-D":       "영상 (검문소 C)",
    "TTFB(초)":   "시스템 (검문소 D)",
    "FPS":         "시스템 (검문소 D)",
    "완료율(%)":  "시스템 (검문소 D)",
}


# ────────────────────────────────────────────────────────────────
# 보고서 출력
# ────────────────────────────────────────────────────────────────

def _print_report(metrics: dict[str, float | None], out_path: Path | None) -> None:
    print("\n" + "=" * 70)
    print("§ 7 최종 평가표")
    print("=" * 70)
    print(f"{'레이어':<22} {'지표':<14} {'우리 결과':>10} {'목표':>10} {'확인':>6}")
    print("-" * 70)

    rows = []
    for key, value in metrics.items():
        layer = _LAYER_MAP.get(key, "기타")
        if key in _GOALS:
            goal_str, check_fn = _GOALS[key]
            if value is None:
                ok = "⬜"
                val_str = "미입력"
            else:
                ok = "✅" if check_fn(value) else "❌"
                val_str = str(value)
        else:
            goal_str, ok, val_str = "-", "⬜", str(value) if value is not None else "미입력"

        print(f"{layer:<22} {key:<14} {val_str:>10} {goal_str:>10} {ok:>6}")
        rows.append({"layer": layer, "metric": key, "value": value, "goal": goal_str, "pass": ok})

    print("=" * 70)

    if out_path:
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump({"metrics": metrics, "table": rows}, f, ensure_ascii=False, indent=2)
        print(f"\n보고서 저장 → {out_path}")


# ────────────────────────────────────────────────────────────────
# 메인
# ────────────────────────────────────────────────────────────────

def run(
    geval_path: Path | None,
    cer_path: Path | None,
    syncnet_path: Path | None,
    system_path: Path | None,
    out_path: Path | None,
) -> None:
    metrics: dict[str, float | None] = {}

    # 검문소 A — G-Eval
    if geval_path and geval_path.exists():
        print(f"[A] G-Eval 로드: {geval_path}")
        metrics.update(_load_geval(geval_path))
    else:
        print("[A] G-Eval 결과 없음 — python -m ai.llm.g_eval 먼저 실행하세요")
        for k in ("consistency", "usefulness", "naturalness", "ethics"):
            metrics[k] = None

    # 검문소 B — CER/WER
    if cer_path and cer_path.exists():
        print(f"[B] CER 로드: {cer_path}")
        metrics.update(_load_cer(cer_path))
    else:
        print("[B] CER 결과 없음 — 정환주님 analyze_stt.py 결과를 JSON으로 전달해 주세요")
        metrics["CER"] = None
        metrics["WER"] = None

    # 검문소 C — SyncNet
    if syncnet_path and syncnet_path.exists():
        print(f"[C] SyncNet 로드: {syncnet_path}")
        metrics.update(_load_syncnet(syncnet_path))
    else:
        print("[C] SyncNet 결과 없음 — 장민수님 LSE-C/D 결과를 JSON으로 전달해 주세요")
        metrics["LSE-C"] = None
        metrics["LSE-D"] = None

    # 검문소 D — 시스템 지표
    if system_path and system_path.exists():
        print(f"[D] 시스템 지표 로드: {system_path}")
        metrics.update(_load_system_metrics(system_path))
    else:
        print("[D] 시스템 지표 없음 — 세종/윤한님·민경이님 결과를 JSON으로 전달해 주세요")
        metrics["TTFB(초)"] = None
        metrics["FPS"] = None
        metrics["완료율(%)"] = None

    _print_report(metrics, out_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="§ 0 검문소 파이프라인 — 전체 평가 취합")
    parser.add_argument("--geval",    type=Path, default=None, help="g_eval.py 결과 JSON (검문소 A)")
    parser.add_argument("--cer",      type=Path, default=None, help="CER 결과 JSON (검문소 B)")
    parser.add_argument("--syncnet",  type=Path, default=None, help="SyncNet 결과 JSON (검문소 C)")
    parser.add_argument("--system",   type=Path, default=None, help="TTFB/FPS/완료율 JSON (검문소 D)")
    parser.add_argument("--out",      type=Path, default=None, help="최종 보고서 저장 경로")
    args = parser.parse_args()

    # geval 기본값: 같은 폴더의 geval_results.json
    if args.geval is None:
        default_geval = Path("geval_results.json")
        if default_geval.exists():
            args.geval = default_geval

    run(args.geval, args.cer, args.syncnet, args.system, args.out)


if __name__ == "__main__":
    main()
