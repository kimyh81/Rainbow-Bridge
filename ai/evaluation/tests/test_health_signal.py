"""수면·활동 → 회복점수 프로토타입 — 순수함수 검증 (더미, DB/실연동 없이)."""

from __future__ import annotations

import pytest

from ..health_signal import (
    activity_to_score,
    blend_recovery_score,
    cross_check,
    health_signal,
    sleep_to_score,
)


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


@pytest.mark.xfail(
    reason="4축 마이그레이션 중 예정된 불일치 — recovery_score는 새 산식"
    "(감정15/지속30/미션40 + 무페널티 재정규화, 06-15 확정)으로 옮겼고 "
    "blend_recovery_score는 아직 옛 산식(40/35/25)이라 둘이 안 맞음. "
    "blend→recovery_score 일원화(B안)는 산식 모세종 합의 + 백엔드 게이트"
    "(emotion.py)·프론트(recovery.js) 정렬 후 진행 예정 → 그때 이 가드 복원.",
    strict=True,
)
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
