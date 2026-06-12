"""health_export_adapter 파서 로직 검증 (합성 CSV).

⚠️ 여기서 검증하는 것 = **파싱 로직**(메타행 스킵·헤더 탐지·컬럼 매칭·집계·날짜 필터)과
   기존 점수 엔진 연결. **실 export 컬럼명 매핑은 미검증(format-v1)** — 실파일로 별도 확정.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from health_export_adapter import (  # noqa: E402
    DUMMY_SLEEP_CSV,
    DUMMY_STEP_CSV,
    from_samsung_export,
    parse_sleep_csv,
    parse_steps_csv,
)
from health_signal import health_signal  # noqa: E402


def test_steps_skips_metadata_row_and_sums():
    # 1행 메타 → 2행 헤더 quirk 를 헤더 자동탐지로 흡수, 합산
    assert parse_steps_csv(DUMMY_STEP_CSV) == 4200


def test_sleep_parses_duration_hours():
    assert parse_sleep_csv(DUMMY_SLEEP_CSV) == 4.5


def test_steps_multiple_rows_sum():
    csv_text = (
        "meta,1\n" "com.samsung.shealth.step_daily_trend.count\n" "1000\n2000\n500\n"
    )
    assert parse_steps_csv(csv_text) == 3500


def test_steps_date_filter():
    csv_text = (
        "meta,1\n"
        "com.samsung.shealth.step_daily_trend.day_time,com.samsung.shealth.step_daily_trend.count\n"
        "2026-06-10,3000\n"
        "2026-06-11,4200\n"
    )
    assert parse_steps_csv(csv_text, date="2026-06-11") == 4200
    assert parse_steps_csv(csv_text, date="2026-06-10") == 3000


def test_steps_epoch_date_filter():
    # 실 발표 경로: epoch ms day_time + date 필터(UTC 고정이라 머신 tz 무관·결정적)
    csv_text = (
        "meta,1\n"
        "com.samsung.shealth.step_daily_trend.day_time,com.samsung.shealth.step_daily_trend.count\n"
        "1781049600000,3000\n"  # 2026-06-10 00:00 UTC
        "1781136000000,4200\n"  # 2026-06-11 00:00 UTC
    )
    assert parse_steps_csv(csv_text, date="2026-06-11") == 4200
    assert parse_steps_csv(csv_text, date="2026-06-10") == 3000


def test_date_filter_without_date_column_returns_none():
    # M1: date 요청인데 날짜 컬럼 없음 → None(조용한 전체 합산 금지). date 없으면 전체합산 유지.
    csv_text = "m\ncom.samsung.shealth.step_daily_trend.count\n1000\n2000\n"
    assert parse_steps_csv(csv_text, date="2026-06-11") is None
    assert parse_steps_csv(csv_text) == 3000


def test_date_filter_excludes_short_rows():
    # M2: 날짜 컬럼보다 짧은(날짜 불명) 행은 필터를 우회해 합산되면 안 됨
    csv_text = (
        "m\n"
        "com.samsung.shealth.step_daily_trend.count,com.samsung.shealth.step_daily_trend.day_time\n"
        "4200,2026-06-11\n"
        "5000\n"  # 날짜 불명 짧은 행 → 제외돼야 함
    )
    assert parse_steps_csv(csv_text, date="2026-06-11") == 4200


def test_overflow_value_graceful():
    # L1: inf 변환(int(float('1e999')))이 크래시하지 않고 건너뜀
    csv_text = "m\ncom.samsung.shealth.step_daily_trend.count\n1e999\n4200\n"
    assert parse_steps_csv(csv_text) == 4200


def test_sleep_date_filter_by_start():
    csv_text = (
        "meta,1\n"
        "com.samsung.shealth.sleep.start_time,com.samsung.shealth.sleep.end_time\n"
        "2026-06-10 23:00:00,2026-06-11 07:00:00\n"  # 취침일 06-10, 8h
        "2026-06-11 23:30:00,2026-06-12 05:30:00\n"  # 취침일 06-11, 6h
    )
    assert parse_sleep_csv(csv_text, date="2026-06-10") == 8.0
    assert parse_sleep_csv(csv_text, date="2026-06-11") == 6.0


def test_unknown_columns_return_none():
    # 컬럼명이 후보에 하나도 없으면 graceful None (크래시 X)
    assert parse_steps_csv("foo,bar\n1,2\n") is None
    assert parse_sleep_csv("foo,bar\n1,2\n") is None


def test_empty_or_garbage_graceful():
    assert parse_steps_csv("") is None
    assert parse_sleep_csv("") is None
    # count 칸에 쓰레기 → 건너뛰고 None
    bad = "meta\ncom.samsung.shealth.step_daily_trend.count\n\nabc\n"
    assert parse_steps_csv(bad) is None


def test_from_samsung_export_matches_health_connect_contract():
    # 출력 키·타입이 health_adapter.from_health_connect 와 동일해야 엔진에 그대로 꽂힘
    out = from_samsung_export(DUMMY_STEP_CSV, DUMMY_SLEEP_CSV)
    assert set(out.keys()) == {"steps", "sleep_hours"}
    assert out == {"steps": 4200, "sleep_hours": 4.5}


def test_only_one_source_present():
    assert from_samsung_export(steps_csv=DUMMY_STEP_CSV) == {
        "steps": 4200,
        "sleep_hours": None,
    }
    assert from_samsung_export(sleep_csv=DUMMY_SLEEP_CSV) == {
        "steps": None,
        "sleep_hours": 4.5,
    }


def test_real_samsung_export_columns():
    # 실 삼성헬스 export(2026-06-12 검증) 컬럼명으로 회귀 가드.
    # 걸음=count·day_time(epoch ms), 수면=com.samsung.health.sleep.start/end_time
    step_csv = (
        "com.samsung.shealth.step_daily_trend,6320001,6\n"
        "binning_data,count,day_time\n"
        "x,9092,1758067200000\n"  # 2025-09-17 UTC
    )
    sleep_csv = (
        "com.samsung.shealth.sleep,6320001,11\n"
        "com.samsung.health.sleep.start_time,com.samsung.health.sleep.end_time\n"
        "2022-07-31 13:00:00.000,2022-07-31 16:30:00.000\n"  # 3.5h
    )
    assert parse_steps_csv(step_csv) == 9092
    assert parse_sleep_csv(sleep_csv) == 3.5
    assert from_samsung_export(step_csv, sleep_csv) == {
        "steps": 9092,
        "sleep_hours": 3.5,
    }


def test_end_to_end_into_health_signal():
    # export → {steps, sleep_hours} → health_signal 점수 엔진까지 연결
    out = from_samsung_export(DUMMY_STEP_CSV, DUMMY_SLEEP_CSV)
    sig = health_signal(emotion_avg=7, **out)
    assert "recovery_index" in sig
    assert "cross_check" in sig
    assert isinstance(sig["recovery_index"], (int, float))
