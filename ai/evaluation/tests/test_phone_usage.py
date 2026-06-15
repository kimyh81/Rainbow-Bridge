"""휴대폰 앱 사용 로그 분석 — 순수함수 검증 (단말/DB 없이)."""

from __future__ import annotations

from datetime import date

from ..phone_usage import (
    CAT_EDUCATION,
    CAT_ENTERTAINMENT,
    CAT_FINANCE,
    CAT_OTHER,
    CAT_SOCIAL,
    SIGNAL_DISRUPTED,
    SIGNAL_INSUFFICIENT,
    SIGNAL_SPIKE,
    SIGNAL_STABLE,
    SIGNAL_WITHDRAWING,
    analyze_phone_usage,
    normalize_category,
)


def _rec(day: str, category: str, minutes: float, **extra) -> dict:
    return {"date": day, "category": category, "minutes": minutes, **extra}


def _span(start_day: int, count: int) -> list[str]:
    return [f"2026-06-{start_day + i:02d}" for i in range(count)]


# --- 카테고리 정규화(normalize_category) ------------------------------------ #


def test_normalize_category_known_values_case_insensitive():
    assert normalize_category("ENTERTAINMENT") == CAT_ENTERTAINMENT
    assert normalize_category("social") == CAT_SOCIAL
    assert normalize_category("Education") == CAT_EDUCATION
    assert normalize_category("FINANCE") == CAT_FINANCE


def test_normalize_category_unknown_or_empty_is_other():
    assert normalize_category("HEALTH") == CAT_OTHER
    assert normalize_category("") == CAT_OTHER
    assert normalize_category(None) == CAT_OTHER


def test_lv2_real_format_dawn_minutes_drive_late_night():
    """실제 LV2 형식: 시간 단위(by_hour) 없이 카테고리별 '새벽(0-6)' 분만 와도 심야 신호가 동작."""
    recs = []
    for d in _span(1, 4):  # 평소: 새벽 사용 거의 없음
        recs.append(_rec(d, "ENTERTAINMENT", 60, late_night_minutes=0))
    for d in _span(5, 4):  # 최근: 새벽 엔터테인먼트 130분(LV2 '새벽 활동 감지' 값)
        recs.append(_rec(d, "ENTERTAINMENT", 200, late_night_minutes=130))
    out = analyze_phone_usage(recs)
    assert out["late_night"]["recent"] == 130.0
    assert out["signal"] == SIGNAL_DISRUPTED
    # by_hour 가 없으니 취침 역산은 LV3 전까지 생략
    assert out["bedtime"] is None


# --- 데이터 부족 ------------------------------------------------------------ #


def test_insufficient_data():
    recs = [_rec(d, "SOCIAL", 30) for d in _span(1, 3)]  # 3일 < 최소 4일
    out = analyze_phone_usage(recs)
    assert out["signal"] == SIGNAL_INSUFFICIENT
    assert out["screen_time"] is None


def test_unknown_category_excluded_from_mix_but_counted_in_total():
    """미분류(other)는 스크린타임 총합엔 들어가되 category_mix·spike엔 빠진다."""
    recs = [_rec(d, "UNKNOWN_APP", 80) for d in _span(1, 6)]
    recs += [_rec(d, "SOCIAL", 20) for d in _span(1, 6)]
    out = analyze_phone_usage(recs)
    # 총 스크린타임엔 other(80) + social(20) = 100분 포함
    assert out["screen_time"]["recent"] == 100.0
    assert CAT_OTHER not in out["category_mix"]


# --- 안정 ------------------------------------------------------------------- #


def test_stable_when_routine_unchanged():
    recs = []
    for d in _span(1, 8):
        recs.append(_rec(d, "EDUCATION", 30))
        recs.append(_rec(d, "FINANCE", 15))
        recs.append(_rec(d, "SOCIAL", 10))
    out = analyze_phone_usage(recs)
    assert out["signal"] == SIGNAL_STABLE
    assert out["concern_level"] == 0
    assert out["mission_intensity_modifier"] == 0


# --- 위축(withdrawal) ------------------------------------------------------- #


def test_withdrawal_when_active_apps_drop_and_entertainment_dominates():
    """앞 절반: 교육·금융 등 일상 앱 고루. 뒤 절반: 엔터테인먼트만 → 행동 반경 축소(위축)."""
    recs = []
    for d in _span(1, 4):  # 평소: 교육·금융·SNS 고루
        recs.append(_rec(d, "EDUCATION", 40))
        recs.append(_rec(d, "FINANCE", 30))
        recs.append(_rec(d, "SOCIAL", 40))
    for d in _span(5, 4):  # 최근: 엔터테인먼트만
        recs.append(_rec(d, "ENTERTAINMENT", 300))
    out = analyze_phone_usage(recs)
    assert out["signal"] == SIGNAL_WITHDRAWING
    assert out["concern_level"] >= 1
    assert out["mission_intensity_modifier"] == -1
    assert any("행동 반경 축소" in e for e in out["evidence"])


# --- 리듬 교란(심야·취침) --------------------------------------------------- #


def test_disrupted_when_late_night_use_rises():
    recs = []
    for d in _span(1, 4):  # 평소: 심야 사용 거의 없음
        recs.append(_rec(d, "ENTERTAINMENT", 60, by_hour={20: 60}))
    for d in _span(5, 4):  # 최근: 새벽 1~3시 엔터테인먼트
        recs.append(
            _rec(d, "ENTERTAINMENT", 180, by_hour={1: 60, 2: 60, 3: 60})
        )
    out = analyze_phone_usage(recs)
    assert out["signal"] == SIGNAL_DISRUPTED
    assert out["late_night"]["recent"] > out["late_night"]["older"]
    assert any("심야" in e for e in out["evidence"])


def test_bedtime_drift_from_sleep_records():
    """삼성헬스 bedtime 이 점점 늦어지면 '생활 리듬 악화'로 잡힌다."""
    recs = [_rec(d, "SOCIAL", 30) for d in _span(1, 8)]
    sleep = [
        {"date": d, "bedtime": "23:20", "sleep_score": 70} for d in _span(1, 4)
    ] + [{"date": d, "bedtime": "02:30", "sleep_score": 50} for d in _span(5, 4)]
    out = analyze_phone_usage(recs, sleep_records=sleep)
    assert out["bedtime"]["direction"] == "늦어짐"
    assert out["signal"] == SIGNAL_DISRUPTED
    assert any("취침" in e for e in out["evidence"])


# --- 급증(spike) ------------------------------------------------------------ #


def test_spike_when_category_surges():
    """평소 SNS 20분 → 최근 180분(>3배) = 급증."""
    recs = [_rec(d, "SOCIAL", 20) for d in _span(1, 4)]
    recs += [_rec(d, "SOCIAL", 180) for d in _span(5, 4)]
    out = analyze_phone_usage(recs)
    assert out["spikes"]
    assert out["spikes"][0]["category"] == CAT_SOCIAL
    assert out["signal"] == SIGNAL_SPIKE
    assert any("급증" in e or "배" in e for e in out["evidence"])


# --- graceful (LV1 only: by_hour·sleep 없음) -------------------------------- #


def test_graceful_without_hourly_or_sleep():
    """시간대·수면 데이터가 없어도(LV1) 스크린타임·카테고리·급증은 동작."""
    recs = [_rec(d, "ENTERTAINMENT", 234) for d in _span(1, 6)]
    out = analyze_phone_usage(recs)
    assert out["screen_time"] is not None
    assert out["bedtime"] is None
    assert out["sleep_link"] is None
    # 심야 데이터가 없으므로 리듬 교란 신호는 뜨지 않음
    assert not any(f["code"] == "late_night_use" for f in out["findings"])


def test_as_of_window_filters_old_records():
    """as_of 기준 window_days 밖의 오래된 기록은 분석에서 빠진다."""
    old = [_rec(d, "SOCIAL", 30) for d in _span(1, 6)]  # 6/1~6/6
    out = analyze_phone_usage(old, as_of=date(2026, 7, 10), window_days=14)
    # 7/10 기준 14일 창 밖 → 관측 0일 → 데이터 부족
    assert out["signal"] == SIGNAL_INSUFFICIENT
