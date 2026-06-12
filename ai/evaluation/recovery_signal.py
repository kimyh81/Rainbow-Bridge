"""⑧-확장: 일상복귀 신호 — 정량 분석.

목표(피드백): "재생횟수·접속빈도·감정추이로 '앱 쓰니 일상복귀 빨라졌다'를 입증."
감정 점수 추이 + 미션 완료율 + (있으면) 접속/재생 빈도를 묶어 **일상복귀 신호**
(회복 중 / 유지 중 / 주의 필요)를 산출합니다.

설계: [report.py](report.py) 와 동일하게 **순수 함수** — DB 조회는 백엔드/호출부가 하고
여기엔 조회 결과(리스트)를 넣어 줍니다. 그래야 GPU/DB 없이 테스트·시뮬레이션이 됩니다.
`build_report` 통합·엔드포인트 노출은 정환주(report.py)와 합의 후.

데이터 출처(PR #158, 머지됨):
- 접속빈도: `access_logs` 컬렉션(로그인마다 `accessed_at`) → 기간별로 묶어 `access_counts` 로.
- 재생횟수: `MediaAsset.play_count`(누적 카운터). ⚠️ per-play 타임스탬프가 없어 '추세'를
  직접 못 냄 → 재생 이벤트 로그가 생기면 `play_counts`(기간별 시계열)로 연결.

핵심 통찰(피드백): "접속/재생이 줄면서 감정이 오르면 = 일상으로 돌아간 신호."
→ 빈도 '감소'는 감정이 '상승/유지'일 때만 회복 근거로 읽습니다(이탈·방치와 구분).
"""

from __future__ import annotations

from datetime import date
from typing import Any, Iterable, Optional, Sequence

from .health_signal import (  # 수면·활동 객관데이터 확장(프로토타입)
    activity_to_score,
    blend_recovery_score,
    condition_signal,
    sleep_to_score,
)

# 신호 라벨 — 백엔드 get_recovery 의 trend 와 동일 어휘로 맞춥니다(혼선 방지).
SIGNAL_RECOVERING = "회복 중"
SIGNAL_STABLE = "유지 중"
SIGNAL_AT_RISK = "주의 필요"
SIGNAL_INSUFFICIENT = "데이터 부족"

_MIN_CHECKINS = 3  # 신호를 내기 위한 최소 감정 체크인 수
_DELTA = 0.5  # 감정 추이 상승/하락 판정 폭(점) — get_recovery 와 동일
_RECENT_WINDOW = 7  # 회복 점수용 감정 평균 윈도우(최근 N회) — RECOVERY_GATE 설계와 동일


def _scores_oldest_first(checkins: Iterable[dict[str, Any]]) -> list[float]:
    """감정 체크인을 시간순(오래된→최근)으로 정렬해 점수만 뽑습니다."""
    rows = sorted(checkins, key=lambda c: str(c.get("created_at") or ""))
    return [float(c.get("score", 0) or 0) for c in rows]


def _split_avg(series: Sequence[float]) -> tuple[float, float]:
    """시계열을 앞(오래된)·뒤(최근) 절반으로 나눠 각 평균을 냅니다."""
    n = len(series)
    mid = n // 2  # 홀수면 최근 쪽을 한 칸 더 길게
    older = series[:mid] or series[:1]
    recent = series[mid:]
    return sum(older) / len(older), sum(recent) / len(recent)


def _completion_rate(missions: Iterable[dict[str, Any]]) -> Optional[float]:
    """미션 완료율(0~1). 미션이 없으면 None."""
    items = list(missions)
    if not items:
        return None
    done = sum(1 for m in items if m.get("done"))
    return round(done / len(items), 3)


def _freq_trend(counts: Optional[Sequence[float]]) -> Optional[dict[str, Any]]:
    """기간별 빈도 시계열 → 추세 dict. 데이터가 2개 미만이면 None(추세 판단 불가)."""
    if not counts or len(counts) < 2:
        return None
    series = [float(x) for x in counts]
    older, recent = _split_avg(series)
    delta = recent - older
    direction = "감소" if delta < 0 else "증가" if delta > 0 else "유지"
    return {
        "older": round(older, 2),
        "recent": round(recent, 2),
        "delta": round(delta, 2),
        "direction": direction,
    }


_CONSISTENCY_WINDOW = 14  # 꾸준함 산정 창(일) — RECOVERY_GATE 설계와 동일.


def _consistency(
    checkins: Iterable[dict[str, Any]], as_of: Optional[date] = None
) -> Optional[float]:
    """체크인 꾸준함(%) — 최근 14일 중 체크인한 '날 수' / 14 × 100.

    Args:
        checkins: 체크인 목록(`created_at` 보유).
        as_of: 기준일. **주면 그날 기준 14일**(장기 잠수=이탈을 0%로 잡음 — 리뷰 Major 반영).
            None 이면 가장 최근 체크인 날짜(결정적·하위호환). 백엔드는 `date.today()` 주입 권장.

    Returns:
        0~100 꾸준함(%), 날짜 파싱 불가하면 None.
    """
    days: set[date] = set()
    for c in checkins:
        token = str(c.get("created_at") or "")[:10]
        try:
            days.add(date.fromisoformat(token))
        except ValueError:
            continue
    if not days:
        return None
    anchor = as_of if as_of is not None else max(days)
    within = sum(1 for d in days if 0 <= (anchor - d).days < _CONSISTENCY_WINDOW)
    return round(within / _CONSISTENCY_WINDOW * 100, 1)


def recovery_score(
    emotion_avg: float,
    completed_missions: int = 0,
    consistency_pct: Optional[float] = None,
) -> int:
    """회복 점수(0~100) — 감정40 / 미션누적35(sticky, 천장35) / 꾸준함25.

    Args:
        emotion_avg: 감정 점수 평균(1~10). `(avg-1)/9*100` 로 0~100 정규화.
        completed_missions: 완료한 미션 수(누적, sticky — 안 떨어짐). 천장 35점.
        consistency_pct: 체크인한 날 / 14 × 25. 없으면 0 취급.
    """
    e = max(0.0, min(100.0, (emotion_avg - 1) / 9 * 100))
    m = min(35.0, float(completed_missions))  # 1미션=1점, 천장 35
    c = max(
        0.0,
        min(25.0, (consistency_pct / 100 * 25) if consistency_pct is not None else 0.0),
    )
    return max(0, min(100, round(0.40 * e + m + c)))


def compute_recovery_signal(
    emotion_checkins: Iterable[dict[str, Any]],
    missions: Iterable[dict[str, Any]] = (),
    *,
    access_counts: Optional[Sequence[float]] = None,
    play_counts: Optional[Sequence[float]] = None,
    sleep_score: Optional[float] = None,
    sleep_hours: Optional[float] = None,
    steps: Optional[int] = None,
    as_of: Optional[date] = None,
) -> dict[str, Any]:
    """일상복귀 신호를 산출합니다.

    Args:
        emotion_checkins: 감정 체크인 목록 ``[{score, created_at}, ...]``(순서 무관, 내부 정렬).
        missions: 미션 목록 ``[{done: bool}, ...]``. 없으면 완료율 생략.
        access_counts: 기간별 앱 접속 횟수(오래된→최근). `access_logs` 를 일/주 단위로
            묶어 넣습니다. 없으면 생략(graceful).
        play_counts: 기간별 영상 재생 횟수(오래된→최근). 재생 이벤트 로그가 있을 때만.
            ⚠️ `play_count` 누적 카운터만 있으면 시계열이 아니라 못 넣음 → None.
        as_of: 꾸준함 기준일. 백엔드가 `date.today()` 를 주면 **장기 미접속(이탈)** 이 꾸준함
            0% 로 잡힘. None 이면 최근 체크인 기준(하위호환).

    Returns:
        ``{signal, recovery_index, emotion, mission_completion_rate, checkin_consistency,
        access_trend, play_trend, sleep_score, activity_score, cross_check, evidence, reason}``.
        ``recovery_index`` 는 기본 RECOVERY_GATE 40/35/25 산식(`recovery_score`)이지만,
        **활동(걸음) 객관데이터가 들어오면** 40/35/25 + 활동10 가중치를 들어온 항목끼리
        재정규화한 산식(`blend_recovery_score`)으로 교체된다(빠진 외부신호는 분모서 제외 —
        데이터 없다고 페널티 없음). 스케일 동일 0~100. 소비자는 ``scoring`` 값으로 구분.
        **수면은 점수서 제외**(결정문서 §2) — `sleep_score`·`cross_check` 로 표시·교차검증만.
        ``evidence`` 는 그대로 보여줄 수 있는 근거 문장 목록.
    """
    rows = list(emotion_checkins)  # generator 두 번 순회(점수·꾸준함) 대비 materialize.
    scores = _scores_oldest_first(rows)

    if len(scores) < _MIN_CHECKINS:
        # 감정 baseline이 없어 blend 점수는 못 내지만, 들어온 수면·활동은 버리지 않고
        # 정규화값을 그대로 노출(조용히 None 처리하면 "데이터 없음"으로 오해됨).
        sleep_norm = sleep_to_score(sleep_score, sleep_hours)
        activity_norm = activity_to_score(steps)
        evidence = [
            f"감정 체크인이 {len(scores)}회뿐이라 신호를 내기 어려워요(최소 {_MIN_CHECKINS}회)."
        ]
        if sleep_norm is not None or activity_norm is not None:
            evidence.append(
                "수면·활동 데이터는 있으나 체크인이 부족해 아직 점수엔 반영하지 못해요."
            )
        return {
            "signal": SIGNAL_INSUFFICIENT,
            "recovery_index": None,
            "emotion": None,
            "mission_completion_rate": _completion_rate(missions),
            "checkin_consistency": None,
            "access_trend": None,
            "play_trend": None,
            "sleep_score": sleep_norm,
            "activity_score": activity_norm,
            "cross_check": None,
            "condition": None,  # 체크인 부족 → 감정 baseline 없어 컨디션 신뢰 불가
            "scoring": "insufficient",
            "evidence": evidence,
            "reason": "아직 데이터가 적어요. 체크인이 쌓이면 회복 추이를 보여드릴게요.",
        }

    older, recent = _split_avg(scores)
    delta = recent - older
    # 회복 점수용 감정 평균은 '최근 7회'(RECOVERY_GATE). 추이(older/recent)는 전체 사용.
    recent_scores = scores[-_RECENT_WINDOW:]
    avg = sum(recent_scores) / len(recent_scores)

    if delta > _DELTA:
        emo_dir, signal = "상승", SIGNAL_RECOVERING
    elif delta < -_DELTA:
        emo_dir, signal = "하락", SIGNAL_AT_RISK
    else:
        emo_dir, signal = "유지", SIGNAL_STABLE

    completed_missions = sum(1 for m in missions if m.get("done"))
    consistency = _consistency(rows, as_of)
    access = _freq_trend(access_counts)
    play = _freq_trend(play_counts)

    # 회복 점수 — RECOVERY_GATE 40/35/25 산식(감정·미션완료·꾸준함). 단순 avg*10 대체.
    index = recovery_score(avg, completed_missions, consistency)
    # 근거 문장 — 발표/화면에 그대로 노출.
    evidence = [f"감정 점수 {round(older, 1)} → {round(recent, 1)} ({emo_dir})"]
    if completed_missions > 0:
        evidence.append(
            f"미션 누적 {completed_missions}개 완료 ({min(completed_missions, 35)}점)"
        )
    if consistency is not None:
        evidence.append(
            f"체크인 꾸준함 {round(consistency)}% (최근 {_CONSISTENCY_WINDOW}일)"
        )
    for label, trend in (("앱 접속", access), ("영상 재생", play)):
        if not trend:
            continue
        if trend["direction"] == "감소" and signal != SIGNAL_AT_RISK:
            evidence.append(
                f"{label} {trend['older']}→{trend['recent']}회 (감소 — 앱 의존이 줄어드는 회복 신호)"
            )
        else:
            evidence.append(
                f"{label} {trend['older']}→{trend['recent']}회 ({trend['direction']})"
            )

    # 객관데이터(삼성헬스→Health Connect) 반영. 수면은 점수서 제외(결정문서 §2) →
    # 활동(걸음)만 점수 항으로 blend 교체. 수면은 교차검증·표시로만. 미제공이면
    # 위 recovery_score 결과 그대로 — 기존 동작 100% 보존(하위호환).
    sleep_norm = sleep_to_score(sleep_score, sleep_hours)
    activity_norm = activity_to_score(steps)
    health_check: Optional[dict[str, Any]] = None
    condition: Optional[dict[str, Any]] = None
    if activity_norm is not None:  # 활동만 점수 항
        index = blend_recovery_score(
            avg, completed_missions, consistency, activity_norm
        )
        evidence.append(f"활동 {round(activity_norm)}/100")
    if sleep_norm is not None:  # 수면 — 점수 미반영, 교차검증·컨디션·표시만
        evidence.append(f"수면점수 {round(sleep_norm)}/100 (참고 — 점수 미반영)")
        # 객관 수면 + 감정 → 오늘 컨디션 추정(회복점수와 별개 출력). cross_check 재사용.
        cond = condition_signal(avg, sleep_score=sleep_norm)
        health_check = cond["cross_check"]
        condition = {
            "condition": cond["condition"],
            "confidence": cond["confidence"],
        }
        if health_check["note"]:
            evidence.append(f"⚠ {health_check['note']}")

    reason = {
        SIGNAL_RECOVERING: "감정이 오르고 있어요. 일상으로 돌아가는 신호입니다.",
        SIGNAL_STABLE: "큰 변화 없이 안정적으로 지내고 있어요.",
        SIGNAL_AT_RISK: "최근 감정이 가라앉고 있어요. 더 세심한 돌봄이 필요해요.",
    }[signal]

    return {
        "signal": signal,
        "recovery_index": index,  # 0~100. 기본 40/35/25, 활동 제공 시 +활동10(수면 제외)
        "emotion": {
            "older_avg": round(older, 1),
            "recent_avg": round(recent, 1),
            "delta": round(delta, 1),
            "direction": emo_dir,
        },
        "mission_completion_rate": _completion_rate(
            missions
        ),  # 율(0~1) — 키 이름·최상위와 일치
        "checkin_consistency": consistency,
        "access_trend": access,
        "play_trend": play,
        "sleep_score": sleep_norm,
        "activity_score": activity_norm,
        "cross_check": health_check,
        "condition": condition,  # 객관 수면+감정 → 오늘 컨디션(양호/주의/보통)+신뢰도. 점수 별개.
        "scoring": (
            "blend" if activity_norm is not None else "base"
        ),  # 어느 산식인지 명시(활동 반영 여부)
        "evidence": evidence,
        "reason": reason,
    }
