"""load_samsung_export — DB 없이 검증하는 부분(문서 생성·날짜 결정·zip 선택·파싱 연결).

⚠️ 실제 mongo 적재(``--write``) 경로는 외부 DB 의존이라 여기서 검증하지 않는다
   (배선은 POST /health/sync 테스트가 보장). 여기선 "넣을 문서가 올바른가"까지.
"""

from __future__ import annotations

import io
import os
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from health_export_adapter import (  # noqa: E402
    DUMMY_SLEEP_CSV,
    DUMMY_STEP_CSV,
    available_step_dates,
)
from load_samsung_export import (  # noqa: E402
    build_health_log_doc,
    read_export_zip,
)


def _make_zip() -> io.BytesIO:
    """실 export 구조를 흉내낸 in-memory zip(걸음·수면 + 잡음 sleep_stage)."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("x/com.samsung.shealth.step_daily_trend.123.csv", DUMMY_STEP_CSV)
        z.writestr("x/com.samsung.shealth.sleep.123.csv", DUMMY_SLEEP_CSV)
        # 헷갈리기 쉬운 형제 파일들 — 골라지면 안 됨
        z.writestr("x/com.samsung.health.sleep_stage.123.csv", "junk\n")
        z.writestr(
            "x/com.samsung.shealth.tracker.pedometer_step_count.123.csv", "junk\n"
        )
    buf.seek(0)
    return buf


# ── 문서 생성 ────────────────────────────────────────────────────────────────
def test_build_doc_matches_endpoint_shape():
    doc = build_health_log_doc(
        pet_id="p1", date="2025-09-17", steps=9000, sleep_hours=None
    )
    # POST /health/sync 가 쓰는 키 그대로 + 식별용 source
    assert doc["pet_id"] == "p1"
    assert doc["date"] == "2025-09-17"
    assert doc["steps"] == 9000
    assert doc["sleep_hours"] is None
    assert doc["source"] == "samsung_export"
    assert "synced_at" in doc  # datetime


def test_build_doc_keeps_sleep_when_present():
    doc = build_health_log_doc(
        pet_id="p1", date="2022-07-31", steps=None, sleep_hours=3.23
    )
    assert doc["steps"] is None
    assert doc["sleep_hours"] == 3.23


# ── zip 멤버 선택 ─────────────────────────────────────────────────────────────
def test_read_export_zip_picks_right_csvs():
    steps_csv, sleep_csv = read_export_zip(_make_zip())
    # step_daily_trend / shealth.sleep 만 골라야 함(sleep_stage·pedometer 잡음 무시)
    assert steps_csv == DUMMY_STEP_CSV
    assert sleep_csv == DUMMY_SLEEP_CSV
    assert "junk" not in (sleep_csv or "")


def test_read_export_zip_missing_returns_none():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("x/unrelated.csv", "a,b\n1,2\n")
    buf.seek(0)
    steps_csv, sleep_csv = read_export_zip(buf)
    assert steps_csv is None and sleep_csv is None


# ── 날짜 결정 헬퍼(어댑터 공개 함수) ──────────────────────────────────────────
def test_available_step_dates_sorted_unique():
    csv_text = (
        "meta,1\n"
        "com.samsung.shealth.step_daily_trend.day_time,"
        "com.samsung.shealth.step_daily_trend.count\n"
        "1781136000000,4200\n"  # 2026-06-11
        "1781222400000,3000\n"  # 2026-06-12
        "1781136000000,100\n"  # 같은 날 중복 → 1개로
    )
    assert available_step_dates(csv_text) == ["2026-06-11", "2026-06-12"]


def test_available_step_dates_empty_when_no_date_col():
    assert available_step_dates("foo,bar\n1,2\n") == []
