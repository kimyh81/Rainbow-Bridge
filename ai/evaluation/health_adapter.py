"""삼성헬스 → Health Connect → 우리 입력 어댑터 (프로토타입).

`react-native-health-connect` 의 `readRecords('Steps'|'SleepSession', ...)` 결과(JSON)를
받아 [health_signal.py](health_signal.py) 입력(`steps`, `sleep_hours`)으로 변환한다.

⚠️ 삼성헬스 데이터는 **삼성헬스 설정 → Health Connect 동기화 ON** 을 켜야 Health Connect
로 넘어온다(삼성헬스 ≠ Health Connect, 별개 생태계). 실연동은 **개발 빌드** 필요
(Expo Go ❌). 지금은 그 JSON 모양을 흉내낸 **더미**로 변환 로직만 검증한다.

Health Connect 레코드 모양(요약):
  Steps        → {"count": int, "startTime": ISO, "endTime": ISO}
  SleepSession → {"startTime": ISO, "endTime": ISO, "stages": [...]}  # 길이=수면시간
readRecords 응답 → {"records": [위 레코드, ...]}
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional


def _iso(s: str) -> datetime:
    """ISO8601(끝 Z 허용) → datetime. 비문자열(None·숫자 등)은 무효 → ValueError(호출부 graceful skip)."""
    if not isinstance(s, str):
        raise ValueError(f"timestamp must be ISO string, got {type(s).__name__}")
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def total_steps(steps_result: Optional[dict[str, Any]]) -> Optional[int]:
    """Steps readRecords 결과 → 걸음 합계. 레코드 없으면 None.

    ⚠️ 결과 안 레코드를 **무조건 전부 합산**한다 → 호출부는 **단일 일(하루) 범위로
    질의한 결과**만 넘겨야 한다. 여러 날을 한 번에 질의하면 며칠치가 합산돼
    `activity_to_score` 가 과대평가된다(타임존·날짜 버킷팅은 호출부 책임).
    """
    if not steps_result:
        return None
    records = steps_result.get("records", [])
    if not isinstance(records, list) or not records:
        return None  # records 가 리스트 아니면(잘못된 JSON) graceful None
    total = 0
    for r in records:
        try:
            total += int(r.get("count", 0))
        except (TypeError, ValueError):
            continue  # 잘못된 count 는 건너뜀(graceful)
    return total


def total_sleep_hours(sleep_result: Optional[dict[str, Any]]) -> Optional[float]:
    """SleepSession readRecords 결과 → 수면시간 합계(시간). 레코드 없으면 None.

    ⚠️ 레코드를 **무조건 전부 합산**한다 → 호출부는 **단일 밤(하룻밤) 범위로 질의한
    결과**만 넘겨야 한다. 여러 밤을 한 번에 질의하면 합산돼 수면시간이 과대평가된다.
    """
    if not sleep_result:
        return None
    records = sleep_result.get("records", [])
    if not isinstance(records, list):
        return None  # records 가 리스트 아니면(잘못된 JSON) graceful None
    hours = 0.0
    for r in records:
        try:
            dur = (_iso(r["endTime"]) - _iso(r["startTime"])).total_seconds() / 3600
        except (KeyError, ValueError, TypeError):
            continue  # naive/aware 타임스탬프 혼합(TypeError) 등은 건너뜀
        if dur > 0:
            hours += dur
    return round(hours, 2) if hours > 0 else None


def from_health_connect(
    steps_result: Optional[dict[str, Any]] = None,
    sleep_result: Optional[dict[str, Any]] = None,
) -> dict[str, Optional[float]]:
    """Health Connect readRecords 결과 → health_signal 입력 dict.

    Returns: ``{"steps": int|None, "sleep_hours": float|None}`` —
    그대로 ``health_signal(**out)`` 에 펼쳐 넣을 수 있다(삼성헬스 수면점수는
    Health Connect 표준에 없어 시간으로 환산 → sleep_hours 로 전달).
    """
    return {
        "steps": total_steps(steps_result),
        "sleep_hours": total_sleep_hours(sleep_result),
    }


# ── 더미 — 삼성헬스 동기화 결과를 흉내낸 JSON(실연동 전 검증용) ──
DUMMY_STEPS_RESULT: dict[str, Any] = {
    "records": [
        {
            "count": 1800,
            "startTime": "2026-06-11T08:00:00Z",
            "endTime": "2026-06-11T12:00:00Z",
        },
        {
            "count": 2400,
            "startTime": "2026-06-11T12:00:00Z",
            "endTime": "2026-06-11T18:00:00Z",
        },
    ]
}
DUMMY_SLEEP_RESULT: dict[str, Any] = {
    "records": [
        {
            "startTime": "2026-06-11T01:30:00Z",
            "endTime": "2026-06-11T06:00:00Z",
            "stages": [],
        },
    ]
}


if __name__ == "__main__":
    import sys

    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    from health_signal import health_signal  # 직접 실행용(패키지 밖)

    parsed = from_health_connect(DUMMY_STEPS_RESULT, DUMMY_SLEEP_RESULT)
    print("어댑터 변환:", parsed)  # {'steps': 4200, 'sleep_hours': 4.5}
    out = health_signal(emotion_avg=7, **parsed)
    print(
        "회복점수:", out["recovery_index"], "| 교차검증:", out["cross_check"]["status"]
    )
    for e in out["evidence"]:
        print("  -", e)
