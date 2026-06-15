"""get_report 통합 테스트 — 가벼운 페이크 DB로 끝단(recovery_signal 포함) 검증.

실제 MongoDB 없이, async 커서 체인(`find().sort()` async-for / `find_one` / `to_list`)만
흉내 내는 페이크로 DB 조회 → build_report 집계 → ReportResponse 매핑 전 구간을 확인한다.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from app.services.report import get_report

# 유효한 24-hex ObjectId 문자열(소유자 조회 경로가 실제로 타도록).
_PET_ID = "0123456789abcdef01234567"


def _dt(day: int) -> datetime:
    return datetime(2026, 6, day, 9, 0, tzinfo=timezone.utc)


class _FakeCursor:
    """find() 반환 커서 — sort/async-iter/to_list 를 흉내."""

    def __init__(self, docs: list[dict]):
        self._docs = docs

    def sort(self, *args, **kwargs) -> "_FakeCursor":
        return self  # 입력을 이미 정렬해 넣으므로 no-op

    def __aiter__(self):
        async def _gen():
            for d in self._docs:
                yield d

        return _gen()

    async def to_list(self, *args, **kwargs) -> list[dict]:
        return list(self._docs)


class _FakeCollection:
    def __init__(self, docs: list[dict] | None = None, find_one_result=None):
        self._docs = docs or []
        self._find_one_result = find_one_result

    def find(self, *args, **kwargs) -> _FakeCursor:
        return _FakeCursor(self._docs)

    async def find_one(self, *args, **kwargs):
        return self._find_one_result

    async def count_documents(self, *args, **kwargs) -> int:
        return len(self._docs)


class _FakeDB:
    def __init__(self, collections: dict[str, _FakeCollection]):
        self._collections = collections

    def __getitem__(self, name: str) -> _FakeCollection:
        return self._collections[name]


def _fake_mongo(collections: dict[str, _FakeCollection]):
    class _M:
        db = _FakeDB(collections)

    return _M()


@pytest.mark.asyncio
async def test_get_report_full_with_recovery_signal():
    """감정 상승 + 접속 감소 → recovery_signal '회복 중' + access_trend '감소'까지 끝단 검증."""
    emotions = [  # created_at 오름차순(오래된→최근), 점수 상승
        {"created_at": _dt(1), "score": 3},
        {"created_at": _dt(2), "score": 3},
        {"created_at": _dt(3), "score": 4},
        {"created_at": _dt(4), "score": 7},
        {"created_at": _dt(5), "score": 8},
        {"created_at": _dt(6), "score": 8},
    ]
    missions = [
        {"completed": True},
        {"completed": False},
        {"completed": True},
        {"completed": False},
    ]
    llm_logs = [{"kind": "message"}, {"kind": "message"}, {"kind": "crisis"}]
    access_logs = [  # 날짜별 3,2,1 → 감소
        {"accessed_at": _dt(1)},
        {"accessed_at": _dt(1)},
        {"accessed_at": _dt(1)},
        {"accessed_at": _dt(2)},
        {"accessed_at": _dt(2)},
        {"accessed_at": _dt(3)},
    ]
    collections = {
        "emotions": _FakeCollection(emotions),
        "missions": _FakeCollection(missions),
        "llm_logs": _FakeCollection(llm_logs),
        "pets": _FakeCollection(find_one_result={"user_id": 42}),
        "access_logs": _FakeCollection(access_logs),
        "media_assets": _FakeCollection([{"play_count": 5}, {"play_count": 3}]),
        "play_logs": _FakeCollection([]),
        "health_logs": _FakeCollection(find_one_result=None),  # 헬스 없음 → base 경로
    }

    with patch("app.services.report.mongodb", new=_fake_mongo(collections)):
        result = await get_report(_PET_ID, period="2026-06")

    assert result.pet_id == _PET_ID
    assert result.usage["total_calls"] == 3
    assert result.mission_completion_rate == 0.5
    # 감정 추이: score 키로 매핑(끝단 EmotionTrend.score)
    assert [t.score for t in result.emotion_trend] == [3, 3, 4, 7, 8, 8]
    # 핵심: 정량 회복신호가 끝단까지 실려 나온다
    sig = result.recovery_signal
    assert sig["signal"] == "회복 중"
    assert sig["access_trend"]["direction"] == "감소"
    assert any("회복 신호" in e for e in sig["evidence"])


@pytest.mark.asyncio
async def test_get_report_graceful_when_owner_missing():
    """pet 소유자(접속로그) 조회 불가여도 access_trend=None 으로 graceful, 리포트는 정상."""
    emotions = [
        {"created_at": _dt(1), "score": 5},
        {"created_at": _dt(2), "score": 6},
        {"created_at": _dt(3), "score": 6},
    ]
    collections = {
        "emotions": _FakeCollection(emotions),
        "missions": _FakeCollection([]),
        "llm_logs": _FakeCollection([]),
        "pets": _FakeCollection(find_one_result=None),  # 소유자 없음
        "access_logs": _FakeCollection([]),
        "media_assets": _FakeCollection([]),
        "play_logs": _FakeCollection([]),
        "health_logs": _FakeCollection(find_one_result=None),  # 헬스 없음 → base 경로
    }

    with patch("app.services.report.mongodb", new=_fake_mongo(collections)):
        result = await get_report(_PET_ID)

    assert result.recovery_signal["access_trend"] is None
    assert result.recovery_signal["signal"] in {"회복 중", "유지 중"}
    assert result.mission_completion_rate is None


@pytest.mark.asyncio
async def test_get_report_play_logs_feed_recovery_signal():
    """play_logs(날짜별 재생) → recovery_signal 의 play_trend 추세까지 끝단 연결 검증."""
    emotions = [
        {"created_at": _dt(1), "score": 3},
        {"created_at": _dt(2), "score": 4},
        {"created_at": _dt(3), "score": 7},
        {"created_at": _dt(4), "score": 8},
    ]
    play_logs = [  # 날짜별 3,2,1 → 감소 추세
        {"pet_id": _PET_ID, "played_at": _dt(1)},
        {"pet_id": _PET_ID, "played_at": _dt(1)},
        {"pet_id": _PET_ID, "played_at": _dt(1)},
        {"pet_id": _PET_ID, "played_at": _dt(2)},
        {"pet_id": _PET_ID, "played_at": _dt(2)},
        {"pet_id": _PET_ID, "played_at": _dt(3)},
    ]
    collections = {
        "emotions": _FakeCollection(emotions),
        "missions": _FakeCollection([]),
        "llm_logs": _FakeCollection([]),
        "pets": _FakeCollection(find_one_result={"user_id": 42}),
        "access_logs": _FakeCollection([]),
        "media_assets": _FakeCollection([]),
        "play_logs": _FakeCollection(play_logs),
        "health_logs": _FakeCollection(find_one_result=None),  # 헬스 없음 → base 경로
    }

    with patch("app.services.report.mongodb", new=_fake_mongo(collections)):
        result = await get_report(_PET_ID, period="2026-06")

    # 표시용 play_trend(날짜별 리스트)도, recovery_signal 의 추세도 함께 채워진다
    assert [pt.count for pt in result.play_trend] == [3, 2, 1]
    play_trend = result.recovery_signal["play_trend"]
    assert play_trend is not None
    assert play_trend["direction"] == "감소"
    assert any("영상 재생" in e for e in result.recovery_signal["evidence"])


@pytest.mark.asyncio
async def test_get_report_health_logs_reach_recovery_score():
    """삼성헬스 걸음(health_logs)이 실제로 회복점수에 닿는지 — 배선 핵심 검증.

    steps 가 들어오면 회복점수 산식이 base→blend 로 바뀌고 activity_score 가 채워져야 한다.
    (수면은 점수 제외 — sleep_hours 는 score 에 안 들어가고 교차검증·표시로만.)
    """
    emotions = [  # 체크인 3회 이상이라야 insufficient 가 아님
        {"created_at": _dt(1), "score": 7},
        {"created_at": _dt(2), "score": 7},
        {"created_at": _dt(3), "score": 8},
        {"created_at": _dt(4), "score": 8},
    ]
    collections = {
        "emotions": _FakeCollection(emotions),
        "missions": _FakeCollection([{"completed": True}, {"completed": True}]),
        "llm_logs": _FakeCollection([]),
        "pets": _FakeCollection(find_one_result={"user_id": 42}),
        "access_logs": _FakeCollection([]),
        "media_assets": _FakeCollection([]),
        "play_logs": _FakeCollection([]),
        # 삼성헬스 동기화 결과(걸음 9000·수면 8h)가 적재돼 있는 상황
        "health_logs": _FakeCollection(
            find_one_result={"steps": 9000, "sleep_hours": 8.0, "date": "2026-06-05"}
        ),
    }

    with patch("app.services.report.mongodb", new=_fake_mongo(collections)):
        result = await get_report(_PET_ID, period="2026-06")

    sig = result.recovery_signal
    # 핵심: 걸음 데이터가 점수 산식까지 닿아 base→blend 로 전환됐다
    assert sig["scoring"] == "blend"
    # 활동 점수가 채워졌다(9000걸음 → 8000 기준 천장 100)
    assert sig["activity_score"] == 100.0
    # 수면은 점수 항이 아니라 교차검증 쪽으로만 들어간다(sleep_score 존재, 산식엔 미반영)
    assert sig["sleep_score"] is not None
    # 객관 수면+감정 → 컨디션 추정도 응답에 실린다(회복점수 게이트와 별개 출력)
    assert sig["condition"] is not None
    assert sig["condition"]["condition"] in {"양호", "주의", "보통"}
    assert sig["condition"]["confidence"] in {"높음", "낮음"}
