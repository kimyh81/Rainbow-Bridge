"""⑧-확장: 사용 지표 → 관찰 문장(2단계) 테스트 — LLM 없이 규칙·가드·주입 검증.

  1. 규칙 기반(LLM 미주입) — 방향 계산·문장·데드존·graceful
  2. LLM 주입 — 정상 문장 채택 / 깨진·금칙·방향반전 출력 시 규칙 폴백
  3. 가드 — 진단·추측 표현 차단, 방향은 항상 숫자가 정본
"""

from __future__ import annotations

import json
from datetime import date

from ..usage_observation import analyze_usage, summarize_category_logs

# 스크린샷(세종 1단계 수집기) 그대로의 입력.
_SAMPLE = {
    "night_usage": {"today": 57, "avg7": 18},
    "education_usage": {"today": 5, "avg7": 40},
}


# --- 1. 규칙 기반 (generate 미주입) ----------------------------------------- #


def test_rule_based_matches_screenshot_directions():
    """스크린샷: 새벽 활동 증가 · 교육 앱 감소."""
    out = analyze_usage(_SAMPLE)
    assert out["source"] == "rule"
    by_key = {f["key"]: f for f in out["findings"]}
    assert by_key["night_usage"]["direction"] == "증가"
    assert by_key["education_usage"]["direction"] == "감소"
    text = " ".join(out["observations"])
    assert "새벽 활동이 증가했습니다" in text
    assert "교육 관련 앱 사용이 감소했습니다" in text


def test_josa_increase_decrease_particles():
    """받침에 따라 주격조사 이/가 가 자연스럽게 붙는다(활동→활동이, 받침 ㅇ)."""
    out = analyze_usage(_SAMPLE)
    # '새벽 활동'(받침 있음) → '활동이', '교육 관련 앱 사용'(받침 있음) → '사용이'
    text = " ".join(out["observations"])
    assert "새벽 활동이 " in text
    assert "앱 사용이 " in text


def test_deadzone_small_change_is_maintained():
    """미세 변화(5분·15% 미만)는 '유지'로 본다(과대 해석 방지)."""
    out = analyze_usage({"screen_time": {"today": 102, "avg7": 100}})
    assert out["findings"][0]["direction"] == "유지"
    assert "비슷한 수준을 유지" in out["observations"][0]


def test_unknown_key_uses_key_as_label():
    out = analyze_usage({"weird_metric": {"today": 90, "avg7": 10}})
    assert out["findings"][0]["label"] == "weird_metric"
    assert out["findings"][0]["direction"] == "증가"


def test_label_override():
    out = analyze_usage(
        {"night_usage": {"today": 57, "avg7": 18}},
        labels={"night_usage": "심야 사용량"},
    )
    assert out["findings"][0]["label"] == "심야 사용량"
    assert "심야 사용량이 증가했습니다" in out["observations"][0]


# --- graceful: 잘못된/빈 입력 ---------------------------------------------- #


def test_missing_fields_are_skipped():
    out = analyze_usage(
        {
            "good": {"today": 60, "avg7": 10},
            "bad_no_avg": {"today": 60},
            "bad_type": "oops",
        }
    )
    keys = {f["key"] for f in out["findings"]}
    assert keys == {"good"}


def test_empty_metrics():
    out = analyze_usage({})
    assert out == {"observations": [], "findings": [], "source": "none"}


# --- 2. LLM 주입 ------------------------------------------------------------ #


def _fake_generate(payload: dict):
    def _gen(prompt, **kwargs):
        return json.dumps(payload, ensure_ascii=False)

    return _gen


def test_llm_sentences_adopted_when_direction_matches():
    payload = {
        "observations": [
            {"key": "night_usage", "sentence": "최근 새벽 시간대 활동이 증가했습니다."},
            {"key": "education_usage", "sentence": "교육 앱 사용이 감소했습니다."},
        ]
    }
    out = analyze_usage(_SAMPLE, generate=_fake_generate(payload))
    assert out["source"] == "llm"
    assert out["observations"][0] == "최근 새벽 시간대 활동이 증가했습니다."


def test_llm_direction_reversal_falls_back_to_rule():
    """LLM 이 방향을 뒤집으면(증가인데 '감소') 채택하지 않고 규칙 문장으로."""
    payload = {
        "observations": [
            {"key": "night_usage", "sentence": "새벽 활동이 감소했습니다."},  # 틀림
            {"key": "education_usage", "sentence": "교육 앱 사용이 감소했습니다."},
        ]
    }
    out = analyze_usage(_SAMPLE, generate=_fake_generate(payload))
    # night_usage 는 규칙 문장(증가)로 교정
    assert "새벽 활동이 증가했습니다" in out["observations"][0]


def test_llm_diagnostic_wording_is_blocked():
    """진단·추측 표현이 섞이면 규칙 문장으로 폴백(추측 금지 가드)."""
    payload = {
        "observations": [
            {"key": "night_usage", "sentence": "새벽 활동이 증가해 우울이 의심됩니다."},
            {"key": "education_usage", "sentence": "교육 앱 사용이 감소한 것으로 보입니다."},
        ]
    }
    out = analyze_usage(_SAMPLE, generate=_fake_generate(payload))
    # 둘 다 가드 탈락 → 전부 규칙 문장
    assert out["source"] == "rule"
    assert all("우울" not in s and "보입니다" not in s for s in out["observations"])


def test_llm_broken_json_falls_back():
    def _bad_gen(prompt, **kwargs):
        return "이건 JSON 이 아닙니다"

    out = analyze_usage(_SAMPLE, generate=_bad_gen)
    assert out["source"] == "rule"
    assert len(out["observations"]) == 2


def test_llm_exception_falls_back():
    def _raise(prompt, **kwargs):
        raise RuntimeError("LLM down")

    out = analyze_usage(_SAMPLE, generate=_raise)
    assert out["source"] == "rule"
    assert len(out["observations"]) == 2


# --- 3. 어댑터: 세종 PM 카테고리 로그 → today/avg7 요약 ---------------------- #


def _cat_logs():
    """8일치 비식별 카테고리 로그(세종 export 포맷). 6/5~6/11 평소, 6/12 변화."""
    logs = []
    for day in range(5, 12):  # 6/5 ~ 6/11 (직전 7일)
        d = f"2026-06-{day:02d}"
        # EDUCATION 40분/일, 새벽 합 18분/일(ENTERTAINMENT 18)
        logs.append({"date": d, "category": "EDUCATION", "minutes": 40, "late_night_minutes": 0})
        logs.append({"date": d, "category": "ENTERTAINMENT", "minutes": 100, "late_night_minutes": 18})
    # 6/12(오늘): EDUCATION 5분, 새벽 57분(ENTERTAINMENT 56 + SOCIAL 1)
    logs.append({"date": "2026-06-12", "category": "EDUCATION", "minutes": 5, "late_night_minutes": 0})
    logs.append({"date": "2026-06-12", "category": "ENTERTAINMENT", "minutes": 234, "late_night_minutes": 56})
    logs.append({"date": "2026-06-12", "category": "SOCIAL", "minutes": 45, "late_night_minutes": 1})
    return logs


def test_summarize_reconstructs_screenshot_metrics():
    """카테고리 로그 → 스크린샷의 night_usage(57/18)·education_usage(5/40) 복원."""
    metrics = summarize_category_logs(_cat_logs())
    assert metrics["night_usage"] == {"today": 57.0, "avg7": 18.0}
    assert metrics["education_usage"] == {"today": 5.0, "avg7": 40.0}
    # 카테고리 키는 소문자_usage 로 정규화
    assert "entertainment_usage" in metrics


def test_summarize_then_analyze_end_to_end():
    """세종 로그 → 어댑터 → analyze_usage 까지 한 번에 도는지(규칙 경로)."""
    metrics = summarize_category_logs(_cat_logs())
    out = analyze_usage(metrics)
    by_key = {f["key"]: f for f in out["findings"]}
    assert by_key["night_usage"]["direction"] == "증가"
    assert by_key["education_usage"]["direction"] == "감소"
    text = " ".join(out["observations"])
    assert "새벽 활동이 증가했습니다" in text
    assert "교육 관련 앱 사용이 감소했습니다" in text


def test_summarize_as_of_explicit():
    metrics = summarize_category_logs(_cat_logs(), as_of=date(2026, 6, 12))
    assert metrics["education_usage"]["today"] == 5.0


def test_summarize_single_day_has_no_baseline():
    """하루치만 있으면 직전 평균을 낼 수 없어 빈 dict(graceful)."""
    one_day = [
        {"date": "2026-06-12", "category": "EDUCATION", "minutes": 5, "late_night_minutes": 0}
    ]
    assert summarize_category_logs(one_day) == {}


def test_summarize_empty():
    assert summarize_category_logs([]) == {}
