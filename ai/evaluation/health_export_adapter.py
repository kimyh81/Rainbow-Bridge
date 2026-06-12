"""삼성헬스 **개인 데이터 내보내기(export) CSV** → health_signal 입력 어댑터.

폰 개발빌드(Health Connect 실연동)가 준비되기 전까지, 발표용 **실데이터**를 내려받는
백업 경로(메모리 ②경로). 삼성헬스 앱 → 설정 → 개인 데이터 다운로드 → zip 안의 CSV를
파싱해 [health_adapter.py](health_adapter.py) 와 **동일한** 출력 ``{steps, sleep_hours}`` 로
변환한다 → 이미 테스트된 ``health_signal`` / ``compute_recovery_signal`` 에 그대로 꽂힘.

흐름:
    삼성헬스 → [개인 데이터 다운로드] → samsunghealth_*.zip
      ├─ com.samsung.shealth.step_daily_trend.*.csv   → steps(걸음)
      └─ com.samsung.shealth.sleep.*.csv              → sleep_hours(수면시간)
    → from_samsung_export(...) → {"steps": int|None, "sleep_hours": float|None}

⚠️ **미검증(format-v1).** 아래 ``_*_COLS`` 컬럼명과 "1행 메타 → 2행 헤더" 구조는 삼성헬스
   export **일반 구조 기준 가정**이다. export 버전마다 컬럼명이 다르므로, **실제 export 파일
   1건을 받기 전까지 신뢰하지 말 것.** 실파일이 오면 헤더 한 줄만 보고 아래 상수만 맞추면 된다
   (파싱 로직·집계·엔진 연결은 합성 CSV로 검증됨 → tests/test_health_export_adapter.py).
"""

from __future__ import annotations

import csv
from datetime import datetime, timezone
from typing import Iterable, Optional

# ── 컬럼명 후보 (삼성헬스 export 버전마다 다름 → 실파일로 확정) ───────────────
# 앞쪽이 우선. 실파일 헤더에서 처음 매칭되는 이름을 쓴다.
_STEP_COUNT_COLS = (
    "com.samsung.shealth.step_daily_trend.count",
    "count",
    "step_count",
    "steps",
)
_STEP_DATE_COLS = (
    "com.samsung.shealth.step_daily_trend.day_time",  # epoch ms(자정) 로 추정
    "day_time",
    "date",
)
_SLEEP_START_COLS = (
    "com.samsung.shealth.sleep.start_time",
    "start_time",
    "sleep_start_time",
)
_SLEEP_END_COLS = (
    "com.samsung.shealth.sleep.end_time",
    "end_time",
    "sleep_end_time",
)


def _rows(csv_text: str) -> list[list[str]]:
    return [r for r in csv.reader(csv_text.splitlines()) if r]


def _find_header(rows: list[list[str]], wanted: Iterable[str]) -> Optional[int]:
    """원하는 컬럼명 후보 중 하나라도 들어있는 **첫 행**을 헤더로 본다.

    삼성헬스 export 는 1행이 메타데이터(버전 토큰 등)이고 2행이 진짜 헤더인 경우가 많다.
    행 번호를 가정하지 않고 "컬럼명이 보이는 행"을 찾아 그 quirk 를 자동 흡수한다.
    """
    wanted_set = set(wanted)
    for i, row in enumerate(rows):
        if wanted_set & set(c.strip() for c in row):
            return i
    return None


def _pick(header: list[str], candidates: Iterable[str]) -> Optional[int]:
    """헤더에서 후보 컬럼명의 인덱스(처음 매칭) 반환. 없으면 None."""
    norm = [c.strip() for c in header]
    for cand in candidates:
        if cand in norm:
            return norm.index(cand)
    return None


def _to_date(raw: str) -> Optional[str]:
    """day_time 값(epoch ms 또는 날짜 문자열) → 'YYYY-MM-DD'. 못 읽으면 None."""
    raw = raw.strip()
    if not raw:
        return None
    # epoch milliseconds 후보
    if raw.isdigit():
        try:
            # UTC 고정 — 실행 머신 tz 에 따라 날짜가 밀리지 않게(결정적).
            # ⚠️ day_time 이 어느 tz 자정 기준인지는 format-v1 미검증(실파일로 확정).
            return datetime.fromtimestamp(int(raw) / 1000, tz=timezone.utc).strftime(
                "%Y-%m-%d"
            )
        except (ValueError, OSError, OverflowError):
            return None
    # 'YYYY-MM-DD ...' 문자열 후보
    return raw[:10] if len(raw) >= 10 else None


def parse_steps_csv(csv_text: str, *, date: Optional[str] = None) -> Optional[int]:
    """step_daily_trend CSV → 걸음 합. ``date`` 지정 시 그 날짜만, 없으면 전체 합.

    호출부는 **단일 날짜** 데이터만 넘기거나 ``date`` 로 거르는 것을 권장
    (여러 날 합산 시 ``activity_to_score`` 과대평가 — health_adapter 와 동일 계약).
    """
    rows = _rows(csv_text)
    h = _find_header(rows, _STEP_COUNT_COLS)
    if h is None:
        return None
    header = rows[h]
    ci = _pick(header, _STEP_COUNT_COLS)
    if ci is None:
        return None
    di = _pick(header, _STEP_DATE_COLS)
    # M1: date 필터 요청인데 날짜 컬럼을 못 찾으면 필터 보장 불가 → 데이터 없음 취급
    # (step_daily_trend 는 본질이 다일치라 조용한 전체 합산은 과대평가 위험).
    if date is not None and di is None:
        return None

    total = 0
    seen = False
    for row in rows[h + 1 :]:
        if ci >= len(row):
            continue
        if date is not None:
            # M2: 날짜 확인 불가 행(컬럼 누락·짧은 행)은 필터 생략 말고 제외.
            if di >= len(row) or _to_date(row[di]) != date:
                continue
        try:
            total += int(float(row[ci].strip()))
            seen = True
        except (TypeError, ValueError, OverflowError):
            continue  # 빈 칸·잘못된 값·inf 건너뜀(graceful)
    return total if seen else None


def parse_sleep_csv(csv_text: str, *, date: Optional[str] = None) -> Optional[float]:
    """sleep CSV → 수면시간(시간) 합. ``date`` 지정 시 그 날(취침일) 만.

    start_time/end_time 차이를 시간으로 환산해 합산(health_adapter.total_sleep_hours 와 동일).
    """
    rows = _rows(csv_text)
    h = _find_header(rows, _SLEEP_START_COLS)
    if h is None:
        return None
    header = rows[h]
    si = _pick(header, _SLEEP_START_COLS)
    ei = _pick(header, _SLEEP_END_COLS)
    if si is None or ei is None:
        return None

    hours = 0.0
    for row in rows[h + 1 :]:
        if si >= len(row) or ei >= len(row):
            continue
        start, end = _parse_dt(row[si]), _parse_dt(row[ei])
        if start is None or end is None:
            continue
        if date is not None and start.strftime("%Y-%m-%d") != date:
            continue
        dur = (end - start).total_seconds() / 3600
        if dur > 0:
            hours += dur
    return round(hours, 2) if hours > 0 else None


def _parse_dt(raw: str) -> Optional[datetime]:
    """삼성헬스 시각 문자열 → datetime. 흔한 포맷 몇 개 시도, 실패 시 None."""
    raw = raw.strip()
    if not raw:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(raw[: len(raw)], fmt)
        except ValueError:
            continue
    # ISO8601(Z 허용) 최후 시도
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def from_samsung_export(
    steps_csv: Optional[str] = None,
    sleep_csv: Optional[str] = None,
    *,
    date: Optional[str] = None,
) -> dict[str, Optional[float]]:
    """삼성헬스 export CSV 텍스트 → health_signal 입력 dict.

    Returns: ``{"steps": int|None, "sleep_hours": float|None}`` —
    ``health_adapter.from_health_connect`` 와 **출력 동일** → ``health_signal(**out)`` 또는
    ``compute_recovery_signal(..., **out)`` 에 그대로 펼쳐 넣는다.
    """
    return {
        "steps": parse_steps_csv(steps_csv, date=date) if steps_csv else None,
        "sleep_hours": parse_sleep_csv(sleep_csv, date=date) if sleep_csv else None,
    }


# ── 합성 CSV — 가정한 export 구조(1행 메타 → 2행 헤더)를 흉내냄(로직 검증용) ──
# ⚠️ 실 export 컬럼명과 다를 수 있음. 실파일 받으면 이 더미와 위 _*_COLS 를 함께 교정.
DUMMY_STEP_CSV = (
    "com.samsung.shealth.step_daily_trend,1\n"  # 1행: 메타(버전 토큰)
    "com.samsung.shealth.step_daily_trend.day_time,com.samsung.shealth.step_daily_trend.count\n"
    "1781136000000,4200\n"  # 2026-06-11 00:00 UTC → 4200 걸음
)
DUMMY_SLEEP_CSV = (
    "com.samsung.shealth.sleep,1\n"
    "com.samsung.shealth.sleep.start_time,com.samsung.shealth.sleep.end_time\n"
    "2026-06-11 01:30:00.000,2026-06-11 06:00:00.000\n"  # 4.5h
)


if __name__ == "__main__":
    import sys

    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    out = from_samsung_export(DUMMY_STEP_CSV, DUMMY_SLEEP_CSV)
    print("export 변환:", out)  # {'steps': 4200, 'sleep_hours': 4.5}
    print("⚠️ format-v1 미검증 — 실 export 파일로 _*_COLS 확정 필요")
