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
    cross_check,
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
    missions: Iterable[dict[str, Any]], as_of: Optional[date] = None
) -> Optional[float]:
    """미션 완료 꾸준함(%) — 최근 14일 중 미션을 완료한 '날 수' / 14 × 100.

    2026-06-12 재정의: 감정 체크인은 이제 설문이 아니라 AI가 매일 추론하므로
    "체크인한 날"은 항상 거의 100%가 되어 의미를 잃는다. 대신 **유저가 실제로
    행동(미션 완료)한 날**을 꾸준함의 근거로 본다(앱 접속 빈도는 의존 신호일 수
    있어 제외 — 모세종 PM 확정).

    Args:
        missions: 미션 목록. ``done=True`` 이고 완료 날짜(``completed_at`` 또는
            ``date``)가 있는 항목만 셉니다. 날짜 없거나 파싱 불가한 항목은
            건너뜁니다(graceful).
        as_of: 기준일. **주면 그날 기준 14일**(장기 잠수=이탈을 0%로 잡음 — 리뷰 Major 반영).
            None 이면 가장 최근 완료 날짜(결정적·하위호환). 백엔드는 `date.today()` 주입 권장.

    Returns:
        0~100 꾸준함(%). 완료 날짜가 있는 미션이 하나도 없으면 None.
    """
    days: set[date] = set()
    for m in missions:
        if not m.get("done"):
            continue
        token = str(m.get("completed_at") or m.get("date") or "")[:10]
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
    lifestyle_pct: Optional[float] = None,
) -> int:
    """회복 점수 — 감정추세15 / 지속성30 / 미션누적40(sticky, 천장40) / 생활패턴15.

    생활패턴(health 데이터) **무페널티 처리** — 2026-06-15 확정(반소람·정환주):
    `lifestyle_pct` 가 없으면(스마트워치/삼성헬스 미사용 사용자) 그 축을 **분모에서
    빼고 재정규화**한다. 데이터가 없다고 점수가 깎이지 않는다(만점 여전히 100).
    정환주 `health_signal.blend_recovery_score` 옵션 A(재정규화)·결정문서 §2와 같은 원칙.
    → 과거 "없으면 0점·천장 85"(데이터 없는 사용자 페널티)를 폐기.

    Args:
        emotion_avg: 감정 점수 평균(1~10, 체크인 스냅샷). `(avg-1)/9*15` 로 0~15 정규화.
        completed_missions: 완료한 미션 수(누적, sticky — 안 떨어짐). 천장 40점.
        consistency_pct: 미션 완료한 날 / 14 × 30. 핵심 축이라 없어도 분모엔 포함(0 기여).
        lifestyle_pct: 생활패턴 정규화 점수(0~100). 없으면(None) 분모서 제외(무페널티).
    """
    # 핵심 3축(감정·미션·지속성)은 사용자가 채울 수 있어 항상 분모 포함.
    e = max(0.0, min(15.0, (emotion_avg - 1) / 9 * 15))
    m = min(40.0, float(completed_missions))  # 1미션=1점, 천장 40
    c = max(
        0.0,
        min(30.0, (consistency_pct / 100 * 30) if consistency_pct is not None else 0.0),
    )
    earned = e + m + c
    max_w = 15.0 + 40.0 + 30.0  # 핵심 분모 85
    if lifestyle_pct is not None:  # 외부 신호(health) — 있을 때만 분모에 포함
        earned += max(0.0, min(15.0, lifestyle_pct / 100 * 15))
        max_w += 15.0  # → 분모 100
    return max(0, min(100, round(earned / max_w * 100)))


# --- 4축 정규화(미션40/지속성30/생활패턴15/감정추세15) — 06-15 설계 -------------- #
# [[project_recovery_score_axes_redesign_260614]] 확정안. 축별 점수 함수
# (mission_score·consistency_score·emotion_trend_score)와 이를 합성하는
# `recovery_score_from_axes` 까지 구현. 생활패턴(15%)은 전용 함수 미정이라
# 당분간 미리 계산한 `lifestyle_pct` 를 받는다.
# ⚠️ 게이트(backend emotion.py)의 recovery_score → recovery_score_from_axes
# **교체는 아직 안 함** — 감정축 절대→추세 전환이 게이트 동작을 바꿔 안전 민감,
# 모세종·김윤한 합의 + consistency 윈도우(정환주) 정렬 후.

_MISSION_WINDOW = 28  # mission_score 집계 윈도우(일)
_DIFFICULTY_ACTIVE = "active"
_EMOTION_TREND_SCALE = 20.0  # delta(1~10 스케일) × SCALE = 점수 변화폭
_EMOTION_TREND_NEUTRAL = 50.0  # delta=0(유지) 기준점
_EMOTION_TREND_FLOOR = 30.0  # 추세가 나빠져도 이 밑으로는 안 깎임("슬픔=감점 아님")

# 4축 합성 가중치(%) — [[project_recovery_score_axes_redesign_260614]] 확정안.
_W_MISSION = 40.0
_W_CONSISTENCY = 30.0
_W_EMOTION_TREND = 15.0
_W_LIFESTYLE = 15.0


def _group_assigned_by_day(
    missions: Iterable[dict[str, Any]],
) -> dict[date, dict[str, Any]]:
    """미션을 '배정일'(date) 기준으로 묶어 {assigned, completed, active_done} 집계.

    Args:
        missions: ``[{"date": "YYYY-MM-DD", "done": bool, "difficulty"?: str}, ...]``.
            ``date`` 는 그 미션이 *배정된* 날(완료일이 아님). 날짜 파싱 불가 항목은
            건너뜀(graceful). ``difficulty`` 없으면 active 판정에서만 제외(나머지
            동작에는 영향 없음 — 김윤한님 스키마 추가 전까지 graceful).
    """
    grouped: dict[date, dict[str, Any]] = {}
    for m in missions:
        token = str(m.get("date") or "")[:10]
        try:
            day = date.fromisoformat(token)
        except ValueError:
            continue
        g = grouped.setdefault(
            day, {"assigned": 0, "completed": 0, "active_done": False}
        )
        g["assigned"] += 1
        if m.get("done"):
            g["completed"] += 1
            if m.get("difficulty") == _DIFFICULTY_ACTIVE:
                g["active_done"] = True
    return grouped


def mission_score(
    missions: Iterable[dict[str, Any]],
    as_of: Optional[date] = None,
    window_days: int = _MISSION_WINDOW,
) -> float:
    """미션 점수(0~100) — 그날 배정된 미션을 *전부* 완료한 날 수 / 윈도우 × 100.

    난이도(gentle/small/active)·배정 개수와 무관 — "다 했나/안 했나"만 본다
    (`docs/RECOVERY_SCORE_DESIGN.md` §4: gentle 3개든 active 1개든 같은 가치).
    매일 미션이 교체 지급되고 완료하면 재체크 불가라 몰아서/중복 파밍은
    구조적으로 불가능 — 별도 방지장치 불필요.

    Args:
        missions: ``[{"date": "YYYY-MM-DD", "done": bool, "difficulty"?: str}, ...]``.
            ``date`` 는 배정일. 같은 날 여러 건이면 그날의 배정 묶음으로 집계.
        as_of: 기준일. 없으면 데이터의 최신 배정일(결정적, 하위호환).
        window_days: 집계 윈도우(기본 28일).

    Returns:
        0~100. 집계 가능한 날이 없으면 0.0.
    """
    grouped = _group_assigned_by_day(missions)
    if not grouped:
        return 0.0
    anchor = as_of if as_of is not None else max(grouped)
    days_in_window = [d for d in grouped if 0 <= (anchor - d).days < window_days]
    if not days_in_window:
        return 0.0
    full_days = sum(
        1
        for d in days_in_window
        if grouped[d]["assigned"] > 0
        and grouped[d]["completed"] >= grouped[d]["assigned"]
    )
    return round(full_days / window_days * 100, 1)


def consistency_score(
    missions: Iterable[dict[str, Any]],
    as_of: Optional[date] = None,
    window_days: int = _CONSISTENCY_WINDOW,
) -> float:
    """지속성 점수(0~100) — mission_score보다 낮은 기준선.

    그날 (배정수-1)개 이상 완료 **또는** active 미션을 완료했으면 그 날 인정.
    배정이 1개뿐인 날(L0 80~100 구간)은 (배정수-1)=0이 되어 "아무것도 안 해도
    인정"되는 걸 막기 위해 임계값을 최소 1로 floor — 즉 1개 배정일 땐
    mission_score와 동일하게 "그 1개를 완료해야" 인정된다(06-15 확정,
    [[project_recovery_score_axes_redesign_260614]]: L0 80~100 구간은 두 점수
    모두 "active 미션 완료했는지" 하나로 단순화).

    Args:
        missions: mission_score와 동일한 입력 형식.
        as_of: 기준일. 없으면 데이터의 최신 배정일.
        window_days: 집계 윈도우(기본 14일).

    Returns:
        0~100. 집계 가능한 날이 없으면 0.0.
    """
    grouped = _group_assigned_by_day(missions)
    if not grouped:
        return 0.0
    anchor = as_of if as_of is not None else max(grouped)
    days_in_window = [d for d in grouped if 0 <= (anchor - d).days < window_days]
    if not days_in_window:
        return 0.0
    credited = 0
    for d in days_in_window:
        g = grouped[d]
        if g["assigned"] <= 0:
            continue
        threshold = max(g["assigned"] - 1, 1)
        if g["completed"] >= threshold or g["active_done"]:
            credited += 1
    return round(credited / window_days * 100, 1)


def emotion_trend_score(
    emotion_checkins: Iterable[dict[str, Any]],
) -> Optional[float]:
    """감정추세 점수(0~100) — 절대 감정이 아닌 *추세(방향)* 만 본다.

    older_avg→recent_avg 변화(delta, 1~10 스케일)를 50점(유지) 중심으로
    정규화: ``50 + delta × 20``, floor 30(추세가 나빠져도 30 밑으로는 안 깎임 —
    "슬픔은 감점 대상이 아니다"), cap 100.

    체크인 입력은 **기존 설문 체크인**(``score``, 1~10) 그대로 사용 — AI 추론
    체크인이 아니어도 동일하게 동작한다(데이터 소스 무관, 06-15 확인).

    Args:
        emotion_checkins: ``[{"score": 1~10, "created_at": "YYYY-MM-DD"}, ...]``
            (순서 무관, 내부에서 시간순 정렬). `_split_avg` 와 동일하게 앞/뒤
            절반으로 나눠 추세를 본다.

    Returns:
        0~100. 체크인이 `_MIN_CHECKINS` 미만이면 None(추세 판단 불가, graceful).
    """
    scores = _scores_oldest_first(emotion_checkins)
    if len(scores) < _MIN_CHECKINS:
        return None
    older, recent = _split_avg(scores)
    delta = recent - older
    return max(
        _EMOTION_TREND_FLOOR,
        min(100.0, _EMOTION_TREND_NEUTRAL + delta * _EMOTION_TREND_SCALE),
    )


def recovery_score_from_axes(
    missions: Iterable[dict[str, Any]],
    emotion_checkins: Iterable[dict[str, Any]],
    *,
    lifestyle_pct: Optional[float] = None,
    as_of: Optional[date] = None,
) -> int:
    """4축(미션40·지속성30·감정추세15·생활패턴15)을 묶은 회복 점수(0~100).

    [recovery_score]() 의 후속 **일원화 버전** — 미리 계산한 스칼라 대신 원자료
    (미션·감정 체크인 리스트)를 받아 축별 점수 함수(`mission_score`/
    `consistency_score`/`emotion_trend_score`)를 직접 호출해 합성한다.

    **무페널티 재정규화** — *판단할 데이터가 없는* 축은 분모에서 빼고 나머지로
    재정규화한다(만점 100 유지, 06-15 확정):
      - 감정추세: 체크인 3회 미만(`emotion_trend_score`→None)이면 추세를 못 내므로 제외.
      - 생활패턴: `lifestyle_pct=None`(워치/삼성헬스 미사용)이면 제외.
    미션·지속성은 사용자가 앱에서 직접 채우는 **핵심 축**이라 데이터가 없어도
    (0점 기여로) 항상 분모에 포함한다 — 무페널티 대상이 아님.

    ⚠️ 아직 어디서도 호출하지 않는다(추가만, 교체 X). 회복 게이트
    (`backend/app/services/emotion.py`)는 여전히 [recovery_score]()(절대 감정)를
    쓴다. 감정축이 '절대→추세'로 바뀌면 게이트 동작이 달라지므로 **모세종·김윤한
    안전 합의 전 교체 금지**. 또한 consistency 윈도우 14→28(L0 캘리브레이션) 변경은
    **정환주 영역** — 여기선 각 함수 기본 윈도우(미션28·지속성14)를 그대로 쓴다.
    생활패턴 전용 `life_pattern_score` 는 미정이라 당분간 `lifestyle_pct`(미리 계산)를 받는다.

    Args:
        missions: ``[{"date": "YYYY-MM-DD", "done": bool, "difficulty"?: str}, ...]``
            (배정일 기준). `mission_score`/`consistency_score` 입력 형식과 동일.
        emotion_checkins: ``[{"score": 1~10, "created_at": ...}, ...]``(순서 무관).
        lifestyle_pct: 생활패턴 정규화 점수(0~100). 없으면(None) 무페널티 제외.
        as_of: 미션 축 윈도우 기준일. None 이면 데이터 최신 배정일.

    Returns:
        0~100 정수.
    """
    missions = list(missions)
    earned = 0.0
    max_w = 0.0

    # 핵심 축(미션·지속성) — 데이터 없으면 0 기여, 그래도 항상 분모 포함.
    earned += mission_score(missions, as_of) / 100 * _W_MISSION
    max_w += _W_MISSION
    earned += consistency_score(missions, as_of) / 100 * _W_CONSISTENCY
    max_w += _W_CONSISTENCY

    # 감정추세 — 체크인 3회 미만이면 추세 불가 → 무페널티 제외.
    et = emotion_trend_score(emotion_checkins)
    if et is not None:
        earned += et / 100 * _W_EMOTION_TREND
        max_w += _W_EMOTION_TREND

    # 생활패턴 — 외부(health) 신호, 있을 때만 분모 포함(무페널티).
    if lifestyle_pct is not None:
        earned += max(0.0, min(100.0, lifestyle_pct)) / 100 * _W_LIFESTYLE
        max_w += _W_LIFESTYLE

    if max_w == 0:  # 방어적(미션·지속성이 항상 70을 더해 실제로는 도달 불가).
        return 0
    return max(0, min(100, round(earned / max_w * 100)))


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
        missions: 미션 목록 ``[{done: bool, completed_at?/date?}, ...]``. 완료율은
            ``done`` 만 보고, 꾸준함(아래 ``as_of``)은 완료된 항목의 날짜를 봅니다.
            없으면 완료율·꾸준함 모두 생략.
        access_counts: 기간별 앱 접속 횟수(오래된→최근). `access_logs` 를 일/주 단위로
            묶어 넣습니다. 없으면 생략(graceful).
        play_counts: 기간별 영상 재생 횟수(오래된→최근). 재생 이벤트 로그가 있을 때만.
            ⚠️ `play_count` 누적 카운터만 있으면 시계열이 아니라 못 넣음 → None.
        as_of: 꾸준함 기준일. 백엔드가 `date.today()` 를 주면 **장기 미접속(이탈)** 이 꾸준함
            0% 로 잡힘. None 이면 최근 미션 완료일 기준(하위호환).

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
    missions = list(missions)  # generator 두 번 순회(완료율·꾸준함) 대비 materialize.
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
    consistency = _consistency(missions, as_of)
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
            f"미션 완료 꾸준함 {round(consistency)}% (최근 {_CONSISTENCY_WINDOW}일)"
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
    if activity_norm is not None:  # 활동만 점수 항
        index = blend_recovery_score(
            avg, completed_missions, consistency, activity_norm
        )
        evidence.append(f"활동 {round(activity_norm)}/100")
    if sleep_norm is not None:  # 수면 — 점수 미반영, 교차검증·표시만
        evidence.append(f"수면점수 {round(sleep_norm)}/100 (참고 — 점수 미반영)")
        health_check = cross_check(sleep_norm, avg)
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
        "scoring": (
            "blend" if activity_norm is not None else "base"
        ),  # 어느 산식인지 명시(활동 반영 여부)
        "evidence": evidence,
        "reason": reason,
    }
