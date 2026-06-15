import app.core.ai_path  # noqa: F401

from collections import Counter
from typing import Any, Iterable

from bson import ObjectId
from bson.errors import InvalidId

from ai.evaluation.report import build_report

from app.db.mongodb import mongodb
from app.schemas.report import EmotionTrend, PlayTrend, ReportResponse
from app.services.health_lifestyle import get_lifestyle_pct


def _bucket_access_counts(timestamps: Iterable[Any]) -> list[int]:
    """접속 시각 목록 → 날짜별 접속 횟수(오래된→최근).

    recovery_signal 의 ``access_counts`` 입력용 순수 함수(DB 의존 없음 → 단위 테스트 가능).
    access_logs 는 user 단위(`accessed_at`)라 pet 소유자 기준 **근사치**입니다
    (다묘 가정 시 한 소유자 접속이 여러 pet 에 동일 적용됨).
    """
    days: Counter = Counter()
    for ts in timestamps:
        key = ts.date().isoformat() if hasattr(ts, "date") else str(ts)[:10]
        days[key] += 1
    return [days[k] for k in sorted(days)]


async def _owner_access_counts(pet_id: str) -> list[int] | None:
    """pet 소유자의 접속 로그를 날짜별 횟수 시계열로. 조회 실패 시 None(graceful)."""
    try:
        pet = await mongodb.db["pets"].find_one(
            {"_id": ObjectId(pet_id)}, {"user_id": 1}
        )
    except (InvalidId, Exception):
        return None
    if not pet or pet.get("user_id") is None:
        return None
    logs = (
        await mongodb.db["access_logs"]
        .find({"user_id": pet["user_id"]}, {"accessed_at": 1})
        .sort("accessed_at", 1)
        .to_list(None)
    )
    counts = _bucket_access_counts(log.get("accessed_at") for log in logs)
    return counts or None


async def get_report(pet_id: str, period: str | None = None) -> ReportResponse:
    """반려동물별 사용 리포트 집계.

    DB 조회는 여기(백엔드)서 하고, 실제 집계는 ai/evaluation 의 순수 함수
    build_report 에 위임(정환주 ⑧). 컬렉션 필드명을 build_report 입력
    규약(score·done)에 맞춰 정규화해 넘긴다.
    """
    # 감정: DB score 그대로 (build_report 정본 키 = score)
    emotion_checkins = [
        {"created_at": str(doc["created_at"]), "score": doc["score"]}
        async for doc in mongodb.db["emotions"]
        .find({"pet_id": pet_id}, {"score": 1, "created_at": 1})
        .sort("created_at", 1)
    ]

    # 미션: DB 필드 → mission_score/consistency_score 입력 규약으로 정규화
    # date(배정일)=created_at, difficulty, completed_at(꾸준함 날짜용) 포함
    raw_missions = await mongodb.db["missions"].find({"pet_id": pet_id}).to_list(None)
    missions = [
        {
            "done": m.get("completed"),
            "date": (
                m["created_at"].date().isoformat() if m.get("created_at") else None
            ),
            "difficulty": m.get("difficulty"),
            "completed_at": (
                m["completed_at"].date().isoformat() if m.get("completed_at") else None
            ),
        }
        for m in raw_missions
    ]

    # LLM 사용 로그: llm_logs 컬렉션 (messages.count 임시 → 실데이터)
    llm_logs = await mongodb.db["llm_logs"].find({"pet_id": pet_id}).to_list(None)
    # 영상 재생횟수 집계
    play_count = 0
    async for doc in mongodb.db["media_assets"].find(
        {"pet_id": pet_id}, {"play_count": 1}
    ):
        play_count += doc.get("play_count", 0)

    # 로그인 접속 횟수 집계
    pet_doc = await mongodb.db["pets"].find_one(
        {"_id": ObjectId(pet_id)}, {"user_id": 1}
    )
    user_id = pet_doc.get("user_id") if pet_doc else None
    session_count = (
        await mongodb.db["access_logs"].count_documents({"user_id": user_id})
        if user_id
        else 0
    )

    # 앱 접속 빈도(일상복귀 신호 근거) — pet 소유자 기준 근사치
    access_counts = await _owner_access_counts(pet_id)

    # 삼성헬스 객관 신호(health_logs 최근 1건) — POST /health/sync 가 날짜별로 적재.
    # 활동(steps)만 회복점수 반영, 수면(sleep_hours)은 교차검증·표시로만(결정문서 §2).
    # 없으면 {} → build_report 가 기존 40/35/25 산식 그대로(하위호환).
    health_doc = await mongodb.db["health_logs"].find_one(
        {"pet_id": pet_id}, sort=[("date", -1)]
    )
    health = health_doc or {}

    # 생활패턴(15%) — 걸음(40%)+수면(30%)+야간 폰사용(30%) 합성. 없으면 무페널티 제외.
    lifestyle = await get_lifestyle_pct(pet_id)

    # TTS 재생 이벤트 날짜별 집계
    play_docs = await mongodb.db["play_logs"].find({"pet_id": pet_id}).to_list(None)
    play_day_counts: Counter = Counter()
    for doc in play_docs:
        played_at = doc.get("played_at")
        if played_at:
            key = (
                played_at.date().isoformat()
                if hasattr(played_at, "date")
                else str(played_at)[:10]
            )
            play_day_counts[key] += 1
    play_trend_data = [
        PlayTrend(date=k, count=v) for k, v in sorted(play_day_counts.items())
    ]

    report = build_report(
        pet_id,
        period,
        llm_logs=llm_logs,
        emotion_checkins=emotion_checkins,
        missions=missions,
        access_counts=access_counts,
        # play_trend(날짜 오름차순)의 횟수만 시계열로 → recovery_signal 재생 빈도 추세 근거
        play_counts=[pt.count for pt in play_trend_data],
        play_count=play_count,
        session_count=session_count,
        sleep_hours=health.get("sleep_hours"),
        steps=health.get("steps"),
        lifestyle_pct=lifestyle,
    )

    return ReportResponse(
        pet_id=report["pet_id"],
        period=report["period"],
        usage=report["usage"],
        emotion_trend=[
            EmotionTrend(created_at=str(row["created_at"]), score=row["score"])
            for row in report["emotion_trend"]
        ],
        play_trend=play_trend_data,
        mission_completion_rate=report["mission_completion_rate"],
        recovery_signal=report["recovery_signal"],
        revisit=report["revisit"],
        play_count=report["play_count"],
        session_count=report["session_count"],
    )
