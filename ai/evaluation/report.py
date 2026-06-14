"""⑧ 평가 리포트 집계 (골격).

지표(초안, 팀 합의): 사용 횟수 · 감정 변화 추이 · 미션 완료율 · 재방문.

설계 원칙: 집계 함수는 **순수 함수**로 둡니다. DB 조회는 백엔드(김윤한)가 하고,
여기엔 조회 결과(리스트)를 넣어 줍니다. 그래야 GPU/DB 없이도 테스트 가능합니다.
(`build_report` 가 데이터를 인자로 받는 이유)

🚧 감정 추이·재방문 등 일부 지표는 백엔드 스키마(②감정체크인·⑥타임라인) 확정 후
   필드명을 맞춰야 합니다 — TODO 표시.
"""

from __future__ import annotations

from collections import Counter
from datetime import date
from typing import Any, Iterable, Optional, Sequence

from .recovery_signal import compute_recovery_signal


def _completion_rate(missions: Iterable[dict[str, Any]]) -> Optional[float]:
    """미션 완료율(0~1). 미션이 없으면 None."""
    items = list(missions)
    if not items:
        return None
    done = sum(1 for m in items if m.get("done"))
    return round(done / len(items), 3)


def _emotion_trend(checkins: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """감정 체크인을 시간순으로 정리한 추이 데이터(프론트 차트용).

    필드명은 백엔드 정본(`backend/.../schemas/emotion.py` `score: int`)에 맞춥니다.
    {created_at, score} 를 시간순 정렬해 넘깁니다.
    """
    rows = [
        {"created_at": c.get("created_at"), "score": c.get("score")} for c in checkins
    ]
    return sorted(rows, key=lambda r: str(r["created_at"]))


def build_report(
    pet_id: str,
    period: Optional[str] = None,
    *,
    llm_logs: Iterable[dict[str, Any]] = (),
    emotion_checkins: Iterable[dict[str, Any]] = (),
    missions: Iterable[dict[str, Any]] = (),
    access_counts: Optional[Sequence[float]] = None,
    play_counts: Optional[Sequence[float]] = None,
    play_count: int = 0,
    session_count: int = 0,
    sleep_score: Optional[float] = None,
    sleep_hours: Optional[float] = None,
    steps: Optional[int] = None,
    as_of: Optional[date] = None,
) -> dict[str, Any]:
    """반려동물별 사용 데이터를 리포트로 집계합니다.

    Args:
        pet_id: 대상 반려동물.
        period: 집계 기간 라벨(예: "2026-06"). 필터링은 호출부(백엔드)에서.
        llm_logs: `llm_logs` 조회 결과(이미 pet_id·기간으로 필터됨).
        emotion_checkins: 감정 체크인 조회 결과(`score`, `created_at`).
        missions: 미션 조회 결과(`done`).
        access_counts: 기간별 앱 접속 횟수(오래된→최근). `access_logs` 를 일/주 단위로
            묶어 넣으면 일상복귀 신호의 '의존 감소' 근거로 쓰입니다. 없으면 생략(graceful).
        play_counts: 기간별 영상/음성 재생 횟수(오래된→최근). `play_logs`(per-play 타임스탬프)
            를 날짜별로 묶어 넣으면 recovery_signal 의 '재생 빈도 추세' 근거로 쓰입니다.
            누적 카운터 `play_count` 와 달리 시계열이라 추세 계산 가능. 없으면 생략(graceful).
        sleep_score: 삼성헬스(→Health Connect) 수면점수 0~100. 넘기면 recovery_signal 의
            회복점수가 수면·활동 재정규화 산식으로 바뀌고 주관·객관 교차검증이 실립니다.
        sleep_hours: 수면점수 없을 때 수면시간(시간)으로 환산(어댑터 `from_health_connect`).
        steps: 걸음수 → 활동점수. 위 셋 모두 없으면 기존 동작 그대로(하위호환).
        as_of: 꾸준함 기준일(보통 `date.today()`). 백엔드 `get_report` 가 넘기면 장기 미접속
            (이탈)이 꾸준함 0% 로 잡힘. None 이면 최근 체크인 기준(하위호환).

    Returns:
        프론트 차트/요약 UI 용 리포트 dict.
        (출력 스키마는 민경이와 확정 후 고정 — TODO)
    """
    logs = list(llm_logs)
    # 제너레이터로 들어와도 아래에서 두 번씩 소비하므로 먼저 리스트로 고정.
    checkins = list(emotion_checkins)
    mission_list = list(missions)
    kind_counts = Counter(log.get("kind") for log in logs)

    return {
        "pet_id": pet_id,
        "period": period,
        "usage": {
            "emotions": len(checkins),
            "messages": kind_counts.get("message", 0),
            "missions": sum(1 for m in mission_list if m.get("done")),
            "total_calls": len(logs),
            "by_kind": dict(kind_counts),
        },
        "emotion_trend": _emotion_trend(checkins),
        "mission_completion_rate": _completion_rate(mission_list),
        # 일상복귀 신호(정량) — recovery_signal.py 통합. 접속빈도 + 수면·활동이 차별 근거.
        "recovery_signal": compute_recovery_signal(
            checkins,
            mission_list,
            access_counts=access_counts,
            play_counts=play_counts,
            sleep_score=sleep_score,
            sleep_hours=sleep_hours,
            steps=steps,
            as_of=as_of,
        ),
        # 🚧 재방문(revisit): 세션/접속 로그 스키마 확정 후 추가 (백엔드 합의)
        "revisit": None,
        "play_count": play_count,
        "session_count": session_count,
    }
