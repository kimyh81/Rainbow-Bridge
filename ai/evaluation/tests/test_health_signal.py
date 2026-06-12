"""수면·활동 → 회복점수 프로토타입 — 순수함수 검증 (더미, DB/실연동 없이)."""

from __future__ import annotations

from ..health_signal import (
    activity_to_score,
    blend_recovery_score,
    condition_signal,
    cross_check,
    health_signal,
    sleep_to_score,
)


# ── condition_signal: 객관 수면 + 감정 → 컨디션 추정(회복점수와 별개, 강사 구상) ──
def test_condition_good_when_sleep_and_mood_good():
    # 수면점수 82 + 기분 좋음 → 양호/높음 (강사 예시)
    out = condition_signal(8, sleep_score=82)
    assert out["condition"] == "양호"
    assert out["confidence"] == "높음"


def test_condition_caution_when_both_bad():
    # 수면 나쁨 + 기분 나쁨 → 주의/높음 (일치)
    out = condition_signal(3, sleep_score=35)
    assert out["condition"] == "주의"
    assert out["confidence"] == "높음"


def test_condition_hidden_risk_when_sensor_bad_but_user_ok():
    # 수면 나쁨 + 기분 좋음 → 주의/낮음 (센서는 나쁜데 괜찮다 = 숨은 위험)
    out = condition_signal(8, sleep_score=32)
    assert out["condition"] == "주의"
    assert out["confidence"] == "낮음"
    assert out["cross_check"]["status"] == "mismatch_high_risk"


def test_condition_caution_when_mood_bad_even_if_sleep_good():
    # 기분 나쁨 → 수면 좋아도 '주의'(안전쪽). 수면좋음+기분나쁨이라 불일치 → 신뢰 낮음
    out = condition_signal(3, sleep_score=80)
    assert out["condition"] == "주의"
    assert out["confidence"] == "낮음"


def test_condition_emotion_boundaries():
    # 감정 경계: 6.0=좋음(양호 가능), 4.0=나쁨(주의), 5.0=중간(보통)
    assert condition_signal(6.0, sleep_score=80)["condition"] == "양호"
    assert condition_signal(4.0, sleep_score=80)["condition"] == "주의"
    assert condition_signal(5.0, sleep_score=80)["condition"] == "보통"


def test_condition_from_sleep_hours_and_no_sleep():
    # 수면시간만 있어도 환산되고, 수면 없으면 감정 단독(신뢰도 낮음)
    assert condition_signal(7, sleep_hours=8)["condition"] == "양호"
    no_sleep = condition_signal(8)
    assert no_sleep["condition"] == "양호"
    assert no_sleep["confidence"] == "낮음"  # 수면 없어 보수적
    # 수면 없어도 기분 나쁨이면 주의(안전쪽 — reviewer 비대칭 지적 반영)
    assert condition_signal(3)["condition"] == "주의"


def test_sleep_score_passthrough():
    # 삼성헬스 수면점수(0~100)는 그대로.
    assert sleep_to_score(sleep_score=82) == 82
    assert sleep_to_score(sleep_score=120) == 100  # 클램프
    assert sleep_to_score() is None  # 둘 다 없으면 None


def test_sleep_hours_optimal_and_short():
    assert sleep_to_score(sleep_hours=8) == 100  # 7~9h 최적
    assert sleep_to_score(sleep_hours=5) == 60  # 7-5=2h 부족 → 100-40


def test_activity_score_normalization():
    assert activity_to_score(8000) == 100
    assert activity_to_score(4000) == 50
    assert activity_to_score(0) == 0
    assert activity_to_score(None) is None


def test_blend_full_is_100():
    # 시그니처: (감정, 미션, 꾸준, 활동) — 수면은 점수 항 아님(결정문서 §2).
    # 미션 만점 = 천장 35개(결정문서 §1 정본 캡).
    assert blend_recovery_score(10, 35, 100, 100) == 100  # 모든 항 만점


def test_blend_renormalizes_missing_external_no_penalty():
    # 옵션 A: 외부신호(활동) 빠지면 분모서 제외 → 없다고 안 깎임.
    # 핵심 만점 + 활동 만점 → 100.
    assert blend_recovery_score(10, 35, 100, 100) == 100
    # 외부신호 전무라도 핵심(감정·미션·꾸준) 만점이면 100.
    assert blend_recovery_score(10, 35, 100, None) == 100


def test_blend_core_always_counts():
    # 미션·꾸준 0이면 핵심 분모(40+35+25=100)에 0 기여 → 감정만점 40/100 = 40.
    assert blend_recovery_score(10, 0, None) == 40


def test_blend_equals_base_when_no_activity():
    # 🔴회귀 가드(reviewer 발견): 활동 없으면 blend == base 산식이어야 함.
    # 미션 캡 35로 통일했으므로 미션 항 환산이 base(미션당 1점)와 동일.
    from ..recovery_signal import recovery_score

    for emo, miss, cons in [(10, 35, 100), (5.5, 10, 50), (7, 20, 70), (3, 5, 30)]:
        assert blend_recovery_score(emo, miss, cons, None) == recovery_score(
            emo, miss, cons
        ), (emo, miss, cons)


def test_cross_check_sensor_bad_self_good():
    # 주관·객관 불일치 케이스: 수면 나쁨 + 기분 좋음 → 불일치 플래그.
    out = cross_check(sleep_score=32, emotion_avg=8)
    assert out["mismatch"] is True
    assert out["status"] == "mismatch_high_risk"


def test_cross_check_agree_low():
    out = cross_check(sleep_score=30, emotion_avg=3)
    assert out["mismatch"] is False
    assert out["status"] == "agree_low"


def test_cross_check_unknown_when_missing():
    assert cross_check(None, 8)["status"] == "unknown"


def test_cross_check_sleep_good_emo_bad():
    # 수면 좋음 + 기분 나쁨 → 불일치(수면 외 요인일 수 있음).
    out = cross_check(sleep_score=75, emotion_avg=3)
    assert out["mismatch"] is True
    assert out["status"] == "mismatch"


def test_cross_check_agree_ok_when_mid():
    # 어느 쪽도 극단 아님 → 플래그 없음.
    out = cross_check(sleep_score=55, emotion_avg=5)
    assert out["mismatch"] is False
    assert out["status"] == "agree_ok"


def test_cross_check_boundary_40_not_bad():
    # _SLEEP_BAD=40 은 '<' 비교 → 정확히 40 은 '나쁨' 아님(경계).
    assert cross_check(sleep_score=40, emotion_avg=8)["status"] == "agree_ok"


def test_health_signal_end_to_end():
    out = health_signal(
        emotion_avg=8,
        completed_missions=5,
        consistency_pct=50,
        sleep_score=32,
        steps=2000,
    )
    assert 0 <= out["recovery_index"] <= 100
    assert out["cross_check"]["mismatch"] is True
    assert any("수면점수" in e for e in out["evidence"])
