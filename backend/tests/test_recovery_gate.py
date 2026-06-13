"""회복 게이트(content_unlocked) 로직 단위 테스트.

실제 Redis / MongoDB 없이 순수 계산 로직만 검증합니다.
"""

import pytest
from unittest.mock import AsyncMock, patch

from app.services.emotion import get_recovery


def _make_records(scores: list[int], risks: list[int]) -> list[dict]:
    """테스트용 감정 기록 생성. 최신 기록이 인덱스 0."""
    return [
        {"score": s, "risk_level": r, "created_at": "2026-06-09T00:00:00+00:00"}
        for s, r in zip(scores, risks)
    ]


@pytest.mark.asyncio
async def test_gate_unlocked_when_conditions_met():
    """3회 이상 + 평균 5점 이상 + risk 1 이하 + 회복 추세 → 언락."""
    records = _make_records(
        scores=[8, 7, 6, 5, 6],
        risks=[0, 0, 0, 1, 0],
    )
    with patch(
        "app.services.emotion.get_recent_emotions", new=AsyncMock(return_value=records)
    ), patch(
        "app.services.emotion.get_completed_mission_count",
        new=AsyncMock(return_value=0),
    ), patch(
        "app.services.emotion.get_mission_completed_days",
        new=AsyncMock(return_value=0),
    ):
        result = await get_recovery("pet_test_1")

    assert result.content_unlocked is True


@pytest.mark.asyncio
async def test_gate_locked_when_checkins_too_few():
    """체크인 2회 이하면 잠금 유지."""
    records = _make_records(scores=[9, 8], risks=[0, 0])
    with patch(
        "app.services.emotion.get_recent_emotions", new=AsyncMock(return_value=records)
    ), patch(
        "app.services.emotion.get_completed_mission_count",
        new=AsyncMock(return_value=0),
    ), patch(
        "app.services.emotion.get_mission_completed_days",
        new=AsyncMock(return_value=0),
    ):
        result = await get_recovery("pet_test_2")

    assert result.content_unlocked is False


@pytest.mark.asyncio
async def test_gate_locked_when_avg_score_low():
    """평균 점수 5점 미만이면 잠금 유지."""
    records = _make_records(scores=[3, 4, 2, 3, 4], risks=[0, 0, 0, 0, 0])
    with patch(
        "app.services.emotion.get_recent_emotions", new=AsyncMock(return_value=records)
    ), patch(
        "app.services.emotion.get_completed_mission_count",
        new=AsyncMock(return_value=0),
    ), patch(
        "app.services.emotion.get_mission_completed_days",
        new=AsyncMock(return_value=0),
    ):
        result = await get_recovery("pet_test_3")

    assert result.content_unlocked is False


@pytest.mark.asyncio
async def test_gate_locked_when_crisis():
    """창(window) 내 어디든 risk 2+ 있으면 잠금 유지 — 최신만 보지 않음."""
    records = _make_records(
        scores=[8, 7, 6, 5, 7],
        risks=[0, 0, 2, 0, 0],  # 최신은 0이지만 2회 전에 L3 위기
    )
    with patch(
        "app.services.emotion.get_recent_emotions", new=AsyncMock(return_value=records)
    ), patch(
        "app.services.emotion.get_completed_mission_count",
        new=AsyncMock(return_value=0),
    ), patch(
        "app.services.emotion.get_mission_completed_days",
        new=AsyncMock(return_value=0),
    ):
        result = await get_recovery("pet_test_4")

    assert result.content_unlocked is False


@pytest.mark.asyncio
async def test_allow_first_person_only_when_no_risk():
    """content_unlocked이어도 창 내 risk>0 있으면 1인칭 편지 잠금."""
    records = _make_records(
        scores=[8, 7, 6, 5, 6],
        risks=[0, 0, 0, 1, 0],  # risk=1 기록이 있음
    )
    with patch(
        "app.services.emotion.get_recent_emotions", new=AsyncMock(return_value=records)
    ), patch(
        "app.services.emotion.get_completed_mission_count",
        new=AsyncMock(return_value=0),
    ), patch(
        "app.services.emotion.get_mission_completed_days",
        new=AsyncMock(return_value=0),
    ):
        result = await get_recovery("pet_test_first_person_1")

    assert result.content_unlocked is True  # 일반 컨텐츠는 열림
    assert result.allow_first_person is False  # 1인칭은 잠금


@pytest.mark.asyncio
async def test_allow_first_person_when_all_safe():
    """창 내 risk 전부 0이면 1인칭 편지 허용."""
    records = _make_records(
        scores=[8, 7, 6, 6, 7],
        risks=[0, 0, 0, 0, 0],
    )
    with patch(
        "app.services.emotion.get_recent_emotions", new=AsyncMock(return_value=records)
    ), patch(
        "app.services.emotion.get_completed_mission_count",
        new=AsyncMock(return_value=0),
    ), patch(
        "app.services.emotion.get_mission_completed_days",
        new=AsyncMock(return_value=0),
    ):
        result = await get_recovery("pet_test_first_person_2")

    assert result.content_unlocked is True
    assert result.allow_first_person is True


@pytest.mark.asyncio
async def test_gate_locked_when_worsening_trend():
    """주의 필요 추세이면 잠금 유지."""
    # 최근이 더 낮아지는 패턴 → "주의 필요"
    records = _make_records(
        scores=[3, 3, 7, 8, 9],  # 최신(인덱스0)이 낮음
        risks=[0, 0, 0, 0, 0],
    )
    with patch(
        "app.services.emotion.get_recent_emotions", new=AsyncMock(return_value=records)
    ), patch(
        "app.services.emotion.get_completed_mission_count",
        new=AsyncMock(return_value=0),
    ), patch(
        "app.services.emotion.get_mission_completed_days",
        new=AsyncMock(return_value=0),
    ):
        result = await get_recovery("pet_test_5")

    assert result.content_unlocked is False


@pytest.mark.asyncio
async def test_gate_no_data():
    """데이터 없으면 잠금 유지."""
    with patch(
        "app.services.emotion.get_recent_emotions", new=AsyncMock(return_value=[])
    ), patch(
        "app.services.emotion.get_completed_mission_count",
        new=AsyncMock(return_value=0),
    ), patch(
        "app.services.emotion.get_mission_completed_days",
        new=AsyncMock(return_value=0),
    ):
        result = await get_recovery("pet_test_empty")

    assert result.content_unlocked is False
