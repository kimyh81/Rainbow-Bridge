"""일상복귀 신호 — 순수함수 검증 (DB/LLM 없이)."""

from __future__ import annotations

from datetime import date, timedelta

from ..recovery_signal import (
    SIGNAL_AT_RISK,
    SIGNAL_INSUFFICIENT,
    SIGNAL_RECOVERING,
    SIGNAL_STABLE,
    compute_recovery_signal,
    consistency_score,
    emotion_trend_score,
    mission_score,
    recovery_score,
    recovery_score_from_axes,
)


def _checkins(scores: list[float]) -> list[dict]:
    """오래된→최근 순 점수 리스트를 체크인 목록으로(created_at 부여)."""
    return [
        {"score": s, "created_at": f"2026-06-{i + 1:02d}"} for i, s in enumerate(scores)
    ]


def _done_missions(dates: list[str]) -> list[dict]:
    """완료 날짜 목록을 완료 미션 목록으로(done=True, completed_at 부여)."""
    return [{"done": True, "completed_at": d} for d in dates]


def test_insufficient_data():
    out = compute_recovery_signal(_checkins([4, 5]))
    assert out["signal"] == SIGNAL_INSUFFICIENT
    assert out["recovery_index"] is None


def test_insufficient_surfaces_health_input_not_discarded():
    # 체크인 부족이라 점수는 못 내지만, 들어온 수면·걸음은 버리지 않고 노출(조용히 None 금지).
    out = compute_recovery_signal(_checkins([4, 5]), sleep_score=80, steps=8000)
    assert out["signal"] == SIGNAL_INSUFFICIENT
    assert out["recovery_index"] is None
    assert out["sleep_score"] == 80
    assert out["activity_score"] == 100
    assert any("점수엔 반영하지 못해요" in e for e in out["evidence"])


def test_insufficient_no_health_keeps_none():
    # 헬스 미제공이면 기존대로 None(하위호환).
    out = compute_recovery_signal(_checkins([4, 5]))
    assert out["sleep_score"] is None
    assert out["activity_score"] is None


def test_recovering_when_scores_rise():
    out = compute_recovery_signal(_checkins([3, 3, 4, 7, 8, 8]))
    assert out["signal"] == SIGNAL_RECOVERING
    assert out["emotion"]["direction"] == "상승"


def test_at_risk_when_scores_fall():
    out = compute_recovery_signal(_checkins([8, 7, 7, 4, 3, 3]))
    assert out["signal"] == SIGNAL_AT_RISK
    assert out["emotion"]["direction"] == "하락"


def test_stable_when_flat():
    out = compute_recovery_signal(_checkins([5, 5, 5, 5, 5]))
    assert out["signal"] == SIGNAL_STABLE


def test_health_args_omitted_is_backward_compatible():
    # 수면·활동 미제공 시 — 기존과 동일 동작(하위호환). 새 키는 None.
    rows = _checkins([5, 6, 6, 7, 7, 8])
    base = compute_recovery_signal(rows)
    explicit_none = compute_recovery_signal(rows, sleep_score=None, steps=None)
    assert base["recovery_index"] == explicit_none["recovery_index"]
    assert base["sleep_score"] is None
    assert base["activity_score"] is None
    assert base["cross_check"] is None
    assert base["scoring"] == "base"  # 어느 산식 썼는지 명시


def test_sleep_flagged_but_not_scored():
    # 결정문서 §2: 수면은 점수서 제외 → 교차검증·표시만. 수면만으론 산식 안 바뀜(base).
    rows = _checkins([8, 8, 8, 8, 8, 8])
    out = compute_recovery_signal(rows, sleep_score=30)
    assert out["sleep_score"] == 30
    assert out["cross_check"]["mismatch"] is True  # 수면 나쁨 vs 기분 좋음
    assert out["scoring"] == "base"  # 수면만으론 blend 전환 안 됨
    assert any("점수 미반영" in e for e in out["evidence"])
    # 수면이 점수에 안 들어갔는지: 수면 없이 낸 점수와 동일해야 함.
    base = compute_recovery_signal(rows)
    assert out["recovery_index"] == base["recovery_index"]


def test_activity_switches_to_blend():
    # 활동(걸음)은 점수 항 → scoring blend 로 전환.
    rows = _checkins([8, 8, 8, 8, 8, 8])
    out = compute_recovery_signal(rows, steps=8000)
    assert out["activity_score"] == 100
    assert out["scoring"] == "blend"
    assert any("활동" in e for e in out["evidence"])


def test_unordered_checkins_sorted_by_date():
    """입력 순서가 뒤섞여도 created_at 기준으로 정렬해 추세를 낸다."""
    rows = [
        {"score": 8, "created_at": "2026-06-06"},
        {"score": 3, "created_at": "2026-06-01"},
        {"score": 7, "created_at": "2026-06-05"},
        {"score": 3, "created_at": "2026-06-02"},
        {"score": 4, "created_at": "2026-06-03"},
        {"score": 6, "created_at": "2026-06-04"},
    ]
    out = compute_recovery_signal(rows)
    assert out["signal"] == SIGNAL_RECOVERING


def test_mission_completion_rate():
    missions = [{"done": True}, {"done": True}, {"done": False}, {"done": False}]
    out = compute_recovery_signal(_checkins([5, 5, 6, 6]), missions)
    # 완료율(0~1) — 키 이름·report 최상위와 일치. 완료개수는 evidence 문장으로 노출.
    assert out["mission_completion_rate"] == 0.5  # 2/4 완료
    assert any("미션 누적 2개 완료" in e for e in out["evidence"])


def test_access_decrease_reads_as_recovery_evidence():
    """감정이 오르는 중 + 접속이 줄면 '의존이 줄어드는 회복 신호'로 근거에 잡힌다."""
    out = compute_recovery_signal(
        _checkins([3, 3, 4, 7, 8, 8]), access_counts=[10, 9, 7, 4, 2, 1]
    )
    assert out["access_trend"]["direction"] == "감소"
    assert any("회복 신호" in e for e in out["evidence"])


def test_graceful_without_engagement_or_missions():
    """접속/재생/미션 없이 감정만으로도 동작(자리만 비어 있음)."""
    out = compute_recovery_signal(_checkins([4, 5, 6, 7]))
    assert out["signal"] in {SIGNAL_RECOVERING, SIGNAL_STABLE}
    assert out["access_trend"] is None
    assert out["play_trend"] is None
    assert (
        out["mission_completion_rate"] is None
    )  # 미션 없음 → None(개수 0 아님, 최상위 관례와 일치)


# --- 회복 점수 (RECOVERY_SCORE_DESIGN 15/40/30/15) --------------------------- #


def test_recovery_score_weighted_15_40_30_15():
    """감정추세15·미션40(sticky)·지속성30·생활패턴15 가중합. 모두 만점이면 100, 모두 절반이면 50."""
    assert recovery_score(10, 40, 100, 100) == 100  # E=15·M=40·C=30·L=15
    assert recovery_score(5.5, 20, 50, 50) == 50  # E=7.5·M=20·C=15·L=7.5


def test_recovery_score_clamped_0_100():
    """범위 밖 입력이어도 0~100 보장(음수/초과 클램프)."""
    assert recovery_score(1, 0, 0, 0) == 0  # E=0
    assert recovery_score(0, 0, 0, 0) == 0  # 음수 입력 → 0
    assert recovery_score(11, 40, 100, 100) == 100  # 초과 입력 → 100


# --- 불변식 (예시가 아닌 '어떤 입력이든' 보장) ------------------------------ #


def test_recovery_score_always_in_0_100():
    """어떤 입력(범위 밖 포함)이어도 점수는 0~100."""
    for emo in (0, 1, 5.5, 10, 11, -3):
        for comp in (0, 1, 17, 35, 50):
            for cons in (-10, 0, 50, 100, 150):
                s = recovery_score(emo, comp, cons)
                assert 0 <= s <= 100, (emo, comp, cons, s)


def test_recovery_score_monotonic_in_emotion():
    """미션·꾸준함 고정 시 감정만 올리면 점수는 줄지 않는다(단조)."""
    prev = -1
    for emo in (1, 3, 5, 7, 10):
        s = recovery_score(emo, 17, 50)
        assert s >= prev
        prev = s


def test_consistency_detects_dropout_with_as_of():
    """as_of(오늘) 주면 장기 잠수가 꾸준함 0%로 잡힌다(이탈 탐지)."""
    from datetime import date

    rows = _checkins([5, 6, 7, 5, 6, 7])  # 6/1~6/6 체크인
    missions = _done_missions(["2026-06-01", "2026-06-02", "2026-06-03"])
    # 기본(as_of 없음) = 최근 미션 완료일 기준 → 꾸준함 있음
    assert compute_recovery_signal(rows, missions)["checkin_consistency"] > 0
    # 한 달 뒤 기준 → 14일 창에 0일 → 0%
    out = compute_recovery_signal(rows, missions, as_of=date(2026, 7, 10))
    assert out["checkin_consistency"] == 0.0


def test_consistency_none_without_completion_dates():
    """미션이 있어도 완료 날짜(completed_at/date)가 없으면 꾸준함은 None(graceful)."""
    missions = [{"done": True}, {"done": True}]  # 날짜 없음
    out = compute_recovery_signal(_checkins([5, 5, 6, 6]), missions)
    assert out["checkin_consistency"] is None
    # 완료율은 그대로 집계됨(꾸준함과 독립).
    assert out["mission_completion_rate"] == 1.0


def test_recovery_index_uses_composite_not_avg10():
    """recovery_index 가 단순 avg*10 이 아니라 40/35/25 산식(꾸준함 포함)으로 나온다."""
    missions = [
        {"done": True, "completed_at": "2026-06-04"},
        {"done": False},
    ]  # 완료 1개
    out = compute_recovery_signal(_checkins([5, 5, 6, 6]), missions)
    c = out["checkin_consistency"]
    assert c is not None
    # index == recovery_score(평균, 완료 미션 수, 꾸준함)
    assert out["recovery_index"] == recovery_score(5.5, 1, c)
    # 과거 단순 척도(avg*10=55)와는 다르다(미션·꾸준함 반영).
    assert out["recovery_index"] != round(5.5 * 10)


def test_checkin_consistency_in_output_and_evidence():
    """꾸준함이 출력·근거 문장에 실린다(최근 14일 중 미션 완료한 날 수)."""
    missions = _done_missions([f"2026-06-{i:02d}" for i in range(1, 7)])  # 연속 6일 완료
    out = compute_recovery_signal(_checkins([3, 3, 4, 7, 8, 8]), missions)
    assert out["checkin_consistency"] == round(6 / 14 * 100, 1)
    assert any("미션 완료 꾸준함" in e for e in out["evidence"])


# --- 4축 정규화 (06-15, project_recovery_score_axes_redesign_260614) -------- #


def _assigned(date_str: str, total: int, completed: int, difficulties=None) -> list[dict]:
    """하루치 배정 미션 목록. 앞에서부터 `completed`개를 완료(done=True) 처리."""
    diffs = difficulties or ["gentle"] * total
    return [
        {"date": date_str, "done": i < completed, "difficulty": diffs[i]}
        for i in range(total)
    ]


def test_mission_score_all_or_nothing():
    """배정 개수와 무관하게 '전부완료한 날'만 인정(3/3, 1/1) — 부분완료(2/3)는 0."""
    missions = (
        _assigned("2026-06-01", 3, 3)
        + _assigned("2026-06-02", 3, 2)
        + _assigned("2026-06-03", 1, 1)
        + _assigned("2026-06-04", 1, 0)
    )
    score = mission_score(missions, as_of=date(2026, 6, 4), window_days=28)
    assert score == round(2 / 28 * 100, 1)  # 06-01, 06-03만 인정


def test_mission_score_empty_is_zero():
    assert mission_score([]) == 0.0


def test_mission_score_window_excludes_old_days():
    missions = _assigned("2026-01-01", 3, 3) + _assigned("2026-06-04", 3, 3)
    score = mission_score(missions, as_of=date(2026, 6, 4), window_days=28)
    assert score == round(1 / 28 * 100, 1)  # 1월 데이터는 윈도우 밖


def test_consistency_score_two_of_three_credited():
    missions = _assigned("2026-06-01", 3, 2)
    score = consistency_score(missions, as_of=date(2026, 6, 1), window_days=14)
    assert score == round(1 / 14 * 100, 1)


def test_consistency_score_one_of_three_not_credited():
    missions = _assigned("2026-06-01", 3, 1)
    score = consistency_score(missions, as_of=date(2026, 6, 1), window_days=14)
    assert score == 0.0


def test_consistency_score_single_mission_requires_completion():
    """L0 80~100(미션1개) — 미완료면 인정 안 됨('배정수-1=0 → 항상인정' 버그 방지)."""
    not_done = _assigned("2026-06-01", 1, 0)
    done = _assigned("2026-06-02", 1, 1)
    assert consistency_score(not_done, as_of=date(2026, 6, 1), window_days=14) == 0.0
    assert consistency_score(done, as_of=date(2026, 6, 2), window_days=14) == round(
        1 / 14 * 100, 1
    )


def test_consistency_score_active_completion_credits_partial_day():
    """3개 중 1개(active)만 완료해도 그날은 인정."""
    missions = [
        {"date": "2026-06-01", "done": True, "difficulty": "active"},
        {"date": "2026-06-01", "done": False, "difficulty": "gentle"},
        {"date": "2026-06-01", "done": False, "difficulty": "gentle"},
    ]
    score = consistency_score(missions, as_of=date(2026, 6, 1), window_days=14)
    assert score == round(1 / 14 * 100, 1)


def test_emotion_trend_score_neutral_when_flat():
    rows = _checkins([6, 6, 6, 6])
    assert emotion_trend_score(rows) == 50.0


def test_emotion_trend_score_rises_above_neutral():
    rows = _checkins([3, 3, 8, 8])
    assert emotion_trend_score(rows) > 50.0


def test_emotion_trend_score_floor_30_on_sharp_drop():
    """절대 슬픔은 감점 대상이 아님 — 추세가 크게 나빠져도 30 밑으로는 안 깎임."""
    rows = _checkins([10, 10, 1, 1])
    assert emotion_trend_score(rows) == 30.0


def test_emotion_trend_score_none_when_insufficient():
    assert emotion_trend_score(_checkins([5, 5])) is None


# --- 4축 합성 recovery_score_from_axes (06-15, 일원화 초안) ------------------ #


def _full_days(base: date, n: int) -> list[dict]:
    """base 부터 n일간 매일 미션 1개를 배정·완료한 목록(전부완료)."""
    out: list[dict] = []
    for i in range(n):
        out += _assigned((base + timedelta(days=i)).isoformat(), 1, 1)
    return out


def test_recovery_score_from_axes_all_max_is_100():
    base = date(2026, 6, 1)
    anchor = base + timedelta(days=27)  # 28일 전부완료 → mission/consistency 만점
    checkins = _checkins([1, 1, 3.5, 3.5])  # delta=2.5 → 감정추세 cap 100
    score = recovery_score_from_axes(
        _full_days(base, 28), checkins, lifestyle_pct=100, as_of=anchor
    )
    assert score == 100


def test_recovery_score_from_axes_drops_absent_axes_no_penalty():
    """감정추세(체크인<3)·생활패턴(None) 없으면 분모서 빠짐 — 점수 안 깎임."""
    base = date(2026, 6, 1)
    anchor = base + timedelta(days=27)
    score = recovery_score_from_axes(
        _full_days(base, 28), _checkins([5, 5]), as_of=anchor
    )
    # mission100·consistency100 → (40+30)/(40+30)*100 = 100
    assert score == 100


def test_recovery_score_from_axes_core_axes_count_when_zero():
    """미션 전무면 핵심축(미션·지속성)은 0으로 분모 유지 — 무페널티 대상 아님."""
    score = recovery_score_from_axes([], _checkins([1, 1, 3.5, 3.5]))
    # mission0(40)+consistency0(30)+emotion100(15), lifestyle 제외 → 15/85*100
    assert score == round(15 / 85 * 100)


def test_recovery_score_from_axes_lifestyle_included_when_present():
    """생활패턴이 있으면 분모에 15 추가(있을 때만 포함)."""
    score = recovery_score_from_axes([], _checkins([5, 5]), lifestyle_pct=100)
    # mission0(40)+consistency0(30)+lifestyle100(15), emotion 제외 → 15/85*100
    assert score == round(15 / 85 * 100)
