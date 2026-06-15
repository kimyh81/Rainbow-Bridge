"""삼성헬스→Health Connect 어댑터 — 순수 변환 검증 (더미 JSON)."""

from __future__ import annotations

from ..health_adapter import (
    DUMMY_SLEEP_RESULT,
    DUMMY_STEPS_RESULT,
    from_health_connect,
    total_sleep_hours,
    total_steps,
)


def test_total_steps_sums_records():
    assert total_steps(DUMMY_STEPS_RESULT) == 4200  # 1800 + 2400
    assert total_steps({"records": []}) is None
    assert total_steps(None) is None


def test_total_sleep_hours_from_duration():
    # 01:30 → 06:00 = 4.5시간
    assert total_sleep_hours(DUMMY_SLEEP_RESULT) == 4.5
    assert total_sleep_hours({"records": []}) is None
    assert total_sleep_hours(None) is None


def test_sleep_skips_bad_timestamps():
    bad = {"records": [{"startTime": "nope", "endTime": "nope"}]}
    assert total_sleep_hours(bad) is None


def test_malformed_records_not_list_graceful():
    # records 가 리스트 아닌 잘못된 JSON → 크래시 없이 None (POST /health/sync 500 방지)
    assert total_steps({"records": "oops"}) is None
    assert total_sleep_hours({"records": "oops"}) is None
    assert total_steps({"records": {"count": 1}}) is None
    assert total_sleep_hours({"records": 123}) is None


def test_sleep_skips_null_or_numeric_timestamps():
    # 실연동서 필드 누락(None)·형 불일치(epoch int) → AttributeError 안 터지고 skip.
    null_ts = {"records": [{"startTime": None, "endTime": None, "stages": []}]}
    numeric_ts = {"records": [{"startTime": 1234567890, "endTime": 1234599999}]}
    assert total_sleep_hours(null_ts) is None
    assert total_sleep_hours(numeric_ts) is None


def test_sleep_skips_mixed_tz_timestamps():
    # naive(끝 Z 없음) + aware(Z) 혼합 → TypeError 안 터지고 skip.
    mixed = {
        "records": [
            {"startTime": "2026-06-11T01:00:00", "endTime": "2026-06-11T06:00:00Z"}
        ]
    }
    assert total_sleep_hours(mixed) is None


def test_steps_skips_bad_count():
    # 비숫자 count 는 건너뛰고 정상 count 만 합산.
    res = {"records": [{"count": "bad"}, {"count": 1000}]}
    assert total_steps(res) == 1000


def test_from_health_connect_shape():
    out = from_health_connect(DUMMY_STEPS_RESULT, DUMMY_SLEEP_RESULT)
    assert out == {"steps": 4200, "sleep_hours": 4.5}
    # health_signal 에 그대로 펼쳐넣을 수 있는 모양인지.
    assert set(out) == {"steps", "sleep_hours"}
