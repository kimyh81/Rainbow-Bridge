"""감정 RAG 추론(emotion_inference) — 규칙·가드·주입 검증.

  1. 규칙 기반(LLM 미주입) — 신호별 보정·등급·graceful
  2. LLM 주입 — 정상 문장 채택 / 금칙어·예외 시 규칙 폴백
  3. 불변식 — 점수는 항상 1~10
"""

from __future__ import annotations

import json

from ..emotion_inference import infer_emotion


# --- 1. 규칙 기반 (generate 미주입) ----------------------------------------- #


def test_no_signals_returns_neutral_with_low_confidence():
    out = infer_emotion()
    assert out["emotion_score"] == 5
    assert out["level"] == "보통"
    assert out["confidence"] == "낮음"
    assert out["source"] == "rule"
    assert any("부족" in e for e in out["evidence"])


def test_condition_good_high_confidence_raises_score():
    out = infer_emotion(condition={"condition": "양호", "confidence": "높음"})
    assert out["emotion_score"] == 6  # baseline5 + 1.5 -> round(6.5) == 6
    assert out["confidence"] == "높음"
    assert any("양호" in e for e in out["evidence"])


def test_condition_null_is_graceful_zero_contribution():
    """condition=None(체크인<3·수면데이터없음) 이어도 다른 신호로 동작."""
    out = infer_emotion(condition=None, mission_completion_rate=0.8)
    assert out["emotion_score"] == 6  # baseline5 + mission high(+0.5) -> round(5.5)==6
    assert out["confidence"] == "높음"


def test_watch_level_when_condition_bad_and_cross_check_agrees():
    out = infer_emotion(
        condition={"condition": "주의", "confidence": "높음"},
        cross_check={
            "status": "agree_low",
            "mismatch": False,
            "note": "몸도 마음도 지친 날이에요. 무리하지 말고 충분히 쉬어주세요.",
        },
    )
    # baseline5 -1.5(주의/높음) -1.0(agree_low) = 2.5 -> round(2.5) == 2
    assert out["emotion_score"] == 2
    assert out["level"] == "주의"
    assert "몸도 마음도 지친 날이에요. 무리하지 말고 충분히 쉬어주세요." in out["evidence"]


def test_cross_check_without_note_is_skipped_from_evidence():
    """delta는 적용되지만 note가 없으면 근거 문장엔 안 실림."""
    out = infer_emotion(cross_check={"status": "agree_low", "mismatch": False, "note": None})
    assert out["emotion_score"] == 4  # baseline5 - 1.0
    # agree_low 자체 문장은 없으므로 fallback 문구만 남음
    assert any("부족" in e for e in out["evidence"])


def test_phone_usage_concern_level_lowers_score():
    out = infer_emotion(
        phone_usage={"concern_level": 2, "reason": "바깥·일상 활동이 줄고 화면 안에 머무는 시간이 늘었어요."}
    )
    assert out["emotion_score"] == 4  # baseline5 - 0.5*2
    assert "바깥·일상 활동이 줄고 화면 안에 머무는 시간이 늘었어요." in out["evidence"]


def test_phone_usage_zero_concern_no_effect():
    out = infer_emotion(phone_usage={"concern_level": 0, "reason": "안정적이에요"})
    assert out["emotion_score"] == 5
    assert not any("안정적이에요" in e for e in out["evidence"])


def test_mission_completion_rate_high_and_low():
    high = infer_emotion(mission_completion_rate=0.8)
    low = infer_emotion(mission_completion_rate=0.1)
    mid = infer_emotion(mission_completion_rate=0.5)
    assert high["emotion_score"] == 6  # +0.5 -> round(5.5)==6
    assert low["emotion_score"] == 4  # -0.5 -> round(4.5)==4 (banker's rounding)
    assert mid["emotion_score"] == 5
    assert any("완료율 80%" in e for e in high["evidence"])
    assert any("완료율 10%" in e for e in low["evidence"])


def test_good_level_requires_combined_positive_signals():
    out = infer_emotion(
        condition={"condition": "양호", "confidence": "높음"},
        mission_completion_rate=0.8,
    )
    # baseline5 +1.5(양호/높음) +0.5(미션 80%) = 7.0
    assert out["emotion_score"] == 7
    assert out["level"] == "좋음"


# --- 2. LLM 주입 ------------------------------------------------------------ #


def _fake_generate(sentence: str):
    def _gen(prompt, **kwargs):
        return json.dumps({"sentence": sentence}, ensure_ascii=False)

    return _gen


def test_llm_sentence_adopted_when_clean():
    out = infer_emotion(
        mission_completion_rate=0.8,
        generate=_fake_generate("최근 미션을 꾸준히 이어가고 있는 모습이 관찰됩니다."),
    )
    assert out["source"] == "llm"
    assert out["evidence"][-1] == "최근 미션을 꾸준히 이어가고 있는 모습이 관찰됩니다."
    # 점수는 LLM과 무관하게 규칙값 유지
    assert out["emotion_score"] == 6


def test_llm_diagnostic_wording_falls_back_to_rule():
    out = infer_emotion(
        mission_completion_rate=0.8,
        generate=_fake_generate("우울 증상이 의심됩니다."),
    )
    assert out["source"] == "rule"
    assert all("우울" not in e for e in out["evidence"])
    assert out["emotion_score"] == 6


def test_llm_broken_json_falls_back():
    def _bad_gen(prompt, **kwargs):
        return "이건 JSON이 아닙니다"

    out = infer_emotion(mission_completion_rate=0.8, generate=_bad_gen)
    assert out["source"] == "rule"
    assert out["emotion_score"] == 6


def test_llm_exception_falls_back():
    def _raise(prompt, **kwargs):
        raise RuntimeError("LLM down")

    out = infer_emotion(mission_completion_rate=0.8, generate=_raise)
    assert out["source"] == "rule"
    assert out["emotion_score"] == 6


# --- 3. 불변식 --------------------------------------------------------------- #


def test_score_always_in_1_10():
    conditions = [None, {"condition": "양호", "confidence": "높음"}, {"condition": "주의", "confidence": "높음"}]
    cross_checks = [
        None,
        {"status": "agree_low", "note": "x"},
        {"status": "mismatch_high_risk", "note": "y"},
    ]
    for cond in conditions:
        for cc in cross_checks:
            for concern in (0, 1, 2):
                for rate in (None, 0.0, 0.5, 1.0):
                    out = infer_emotion(
                        condition=cond,
                        cross_check=cc,
                        phone_usage={"concern_level": concern, "reason": "r"},
                        mission_completion_rate=rate,
                    )
                    assert 1 <= out["emotion_score"] <= 10
                    assert out["level"] in {"좋음", "보통", "주의"}
