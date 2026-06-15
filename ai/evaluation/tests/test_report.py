"""⑧ build_report 집계 테스트."""

from __future__ import annotations

from ..report import build_report


def test_empty_report():
    r = build_report("pet1")
    assert r["usage"]["total_calls"] == 0
    assert r["mission_completion_rate"] is None


def test_usage_and_completion():
    logs = [{"kind": "message"}, {"kind": "message"}, {"kind": "crisis"}]
    missions = [{"done": True}, {"done": False}, {"done": True}, {"done": False}]
    r = build_report("pet1", "2026-06", llm_logs=logs, missions=missions)
    assert r["usage"]["total_calls"] == 3
    assert r["usage"]["by_kind"]["message"] == 2
    assert r["mission_completion_rate"] == 0.5


def test_emotion_trend_sorted():
    checkins = [
        {"created_at": "2026-06-02", "score": 3},
        {"created_at": "2026-06-01", "score": 1},
    ]
    r = build_report("pet1", emotion_checkins=checkins)
    scores = [row["score"] for row in r["emotion_trend"]]
    assert scores == [1, 3]  # created_at 오름차순 정렬


def test_recovery_signal_integrated():
    """build_report 가 recovery_signal 을 포함하고, 접속빈도 근거를 반영한다."""
    checkins = [
        {"created_at": f"2026-06-{i + 1:02d}", "score": s}
        for i, s in enumerate([3, 3, 4, 7, 8, 8])
    ]
    r = build_report(
        "pet1", emotion_checkins=checkins, access_counts=[10, 9, 7, 4, 2, 1]
    )
    sig = r["recovery_signal"]
    assert sig["signal"] == "회복 중"
    assert sig["access_trend"]["direction"] == "감소"
    assert any("회복 신호" in e for e in sig["evidence"])


def test_recovery_signal_play_counts_forwarded():
    """build_report 가 play_counts 를 recovery_signal 의 재생 빈도 추세로 연결한다."""
    checkins = [
        {"created_at": f"2026-06-{i + 1:02d}", "score": s}
        for i, s in enumerate([3, 3, 4, 7, 8, 8])
    ]
    r = build_report("pet1", emotion_checkins=checkins, play_counts=[8, 7, 5, 3, 2, 1])
    sig = r["recovery_signal"]
    assert sig["play_trend"]["direction"] == "감소"
    assert any("영상 재생" in e for e in sig["evidence"])


def test_recovery_signal_health_forwarded():
    """build_report 가 sleep_score/steps 를 recovery_signal 까지 끝까지 전달한다(배선)."""
    checkins = [
        {"created_at": f"2026-06-{i + 1:02d}", "score": s}
        for i, s in enumerate([8, 8, 8, 8, 8, 8])  # 감정 높음
    ]
    r = build_report("pet1", emotion_checkins=checkins, sleep_score=30, steps=2000)
    sig = r["recovery_signal"]
    assert sig["sleep_score"] == 30
    assert sig["scoring"] == "axes"  # 06-15 일원화: 항상 recovery_score_from_axes
    assert sig["cross_check"]["mismatch"] is True  # 수면 나쁨 + 기분 좋음
    assert any("수면점수" in e for e in sig["evidence"])


def test_health_omitted_keeps_base_scoring():
    """헬스 미제공 시에도 build_report → recovery_signal 이 정상 동작한다(하위호환)."""
    checkins = [
        {"created_at": f"2026-06-{i + 1:02d}", "score": s}
        for i, s in enumerate([5, 6, 6, 7, 7, 8])
    ]
    r = build_report("pet1", emotion_checkins=checkins)
    assert r["recovery_signal"]["scoring"] == "axes"
    assert r["recovery_signal"]["sleep_score"] is None


def test_recovery_signal_present_without_access():
    """접속빈도 없이도 recovery_signal 자리는 채워진다(graceful)."""
    r = build_report(
        "pet1", emotion_checkins=[{"created_at": "2026-06-01", "score": 5}]
    )
    assert r["recovery_signal"]["signal"] == "데이터 부족"
    assert r["recovery_signal"]["access_trend"] is None


def test_recovery_signal_as_of_forwarded_detects_dropout():
    """build_report 가 as_of 를 recovery_signal 까지 전달 → 장기 잠수 = 꾸준함 0% (종단)."""
    from datetime import date

    checkins = [
        {"created_at": f"2026-06-{i + 1:02d}", "score": s}
        for i, s in enumerate([5, 6, 7, 5, 6, 7])  # 6/1~6/6
    ]
    missions = [
        {"done": True, "completed_at": d} for d in ("2026-06-01", "2026-06-02")
    ]
    # as_of 없으면 최근 미션 완료일 기준 → 꾸준함 있음
    assert (
        build_report("pet1", emotion_checkins=checkins, missions=missions)[
            "recovery_signal"
        ]["checkin_consistency"]
        > 0
    )
    # as_of=한 달 뒤 → 14일 창에 0일 → 이탈로 0%
    r = build_report(
        "pet1", emotion_checkins=checkins, missions=missions, as_of=date(2026, 7, 10)
    )
    assert r["recovery_signal"]["checkin_consistency"] == 0.0
