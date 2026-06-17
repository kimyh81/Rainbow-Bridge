"""슈퍼 계정 demo04 수준으로 시드 (gate=open, allow_1st=True)

super0~5@rainbow.dev / super1234
checkins=[5,6,6,7,7,8,9], health_days=7, missions_days=24 → score ~89

서버에서 실행:
  docker exec rainbow_backend bash -c \
    "sed -i 's|https://rainbow-bridge.duckdns.org|http://localhost:8000|' scripts/seed_super_open.py \
     && python3 scripts/seed_super_open.py \
     && sed -i 's|http://localhost:8000|https://rainbow-bridge.duckdns.org|' scripts/seed_super_open.py"
"""

from __future__ import annotations

import os
import random
import time
from datetime import date, datetime, timedelta, timezone

import httpx
from dotenv import load_dotenv

load_dotenv()

BASE = "https://rainbow-bridge.duckdns.org"
PASSWORD = "super1234"
RESET = True

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "rainbow_bridge")

CHECKINS = [5, 6, 6, 7, 7, 8, 9]
HEALTH_DAYS = 7
MISSIONS_DAYS = 24

ACCOUNTS = [
    {
        "email": "super0@rainbow.dev",
        "nickname": "하늘이보호자",
        "pet_name": "하늘이",
        "gender": "남아",
    },
    {
        "email": "super1@rainbow.dev",
        "nickname": "별이보호자",
        "pet_name": "별이",
        "gender": "여아",
    },
    {
        "email": "super2@rainbow.dev",
        "nickname": "구름이보호자",
        "pet_name": "구름이",
        "gender": "남아",
    },
    {
        "email": "super3@rainbow.dev",
        "nickname": "봄이보호자",
        "pet_name": "봄이",
        "gender": "여아",
    },
    {
        "email": "super4@rainbow.dev",
        "nickname": "달이보호자",
        "pet_name": "달이",
        "gender": "남아",
    },
    {
        "email": "super5@rainbow.dev",
        "nickname": "콩이보호자",
        "pet_name": "콩이",
        "gender": "여아",
    },
]

_MISSION_POOL = [
    ("오늘 산책하기", "15분이라도 밖에 나가 바람을 쐬어보세요.", "activity", "small"),
    (
        "소중한 사람에게 연락하기",
        "가까운 가족이나 친구에게 안부를 전해보세요.",
        "connection",
        "small",
    ),
    (
        "반려동물과의 추억 기록하기",
        "소중한 기억을 글이나 사진으로 남겨보세요.",
        "record",
        "small",
    ),
    ("따뜻한 음료 마시기", "잠깐 쉬며 따뜻한 차 한 잔 마셔보세요.", "rest", "gentle"),
    (
        "좋아하는 음악 듣기",
        "마음이 편한 음악을 들으며 잠시 쉬어가세요.",
        "rest",
        "gentle",
    ),
]


def _mongo_col(name: str):
    from pymongo import MongoClient

    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    return client, client[MONGO_DB_NAME][name]


def _reset_pet_data(pet_id: str):
    try:
        _, emotions = _mongo_col("emotions")
        _, missions = _mongo_col("missions")
        _, health = _mongo_col("health_logs")
        _, usage = _mongo_col("usage_stats")
        r1 = emotions.delete_many({"pet_id": pet_id})
        r2 = missions.delete_many({"pet_id": pet_id})
        r3 = health.delete_many({"pet_id": pet_id})
        r4 = usage.delete_many({"pet_id": pet_id})
        print(
            f"  RESET: 감정 {r1.deleted_count}·미션 {r2.deleted_count}·헬스 {r3.deleted_count}·사용량 {r4.deleted_count} 삭제"
        )
    except Exception as e:
        print(f"  RESET 실패: {e.__class__.__name__}")


def _insert_missions_mongo(pet_id: str, days: int):
    try:
        client, col = _mongo_col("missions")
        today = datetime.now(timezone.utc).replace(
            hour=12, minute=0, second=0, microsecond=0
        )
        for i in range(days):
            past = today - timedelta(days=i + 1)
            m = _MISSION_POOL[i % len(_MISSION_POOL)]
            col.insert_one(
                {
                    "pet_id": pet_id,
                    "title": m[0],
                    "description": m[1],
                    "category": m[2],
                    "difficulty": m[3],
                    "completed": True,
                    "skipped": False,
                    "created_at": past,
                    "completed_at": past,
                }
            )
        client.close()
        print(f"  MongoDB: 과거 {days}일치 미션 삽입")
    except Exception as e:
        print(f"  MongoDB 미션 삽입 실패: {e.__class__.__name__}")


def seed_checkins(c, headers, pet_id):
    for i, score in enumerate(CHECKINS):
        r = c.post(
            "/api/v1/emotions",
            json={"pet_id": pet_id, "score": score, "note": "오늘 하루 잘 버텼어요"},
            headers=headers,
        )
        risk = (
            r.json().get("risk_level", "?")
            if r.status_code == 201
            else f"err({r.status_code})"
        )
        print(f"  체크인 {i+1}: score={score} risk={risk}")
        time.sleep(1.0)


def seed_health(c, headers, pet_id):
    today = date.today()
    for i in range(HEALTH_DAYS):
        d = (today - timedelta(days=i)).isoformat()
        steps = random.randint(5000, 9000)
        sleep_h = round(random.uniform(6.0, 7.5), 1)
        late = random.randint(5, 20)
        c.post(
            "/api/v1/health/sync",
            json={
                "pet_id": pet_id,
                "steps_result": {
                    "records": [
                        {
                            "count": steps,
                            "startTime": f"{d}T08:00:00+09:00",
                            "endTime": f"{d}T08:10:00+09:00",
                        }
                    ]
                },
                "sleep_result": {
                    "records": [
                        {
                            "startTime": f"{d}T00:00:00+09:00",
                            "endTime": f"{d}T{int(sleep_h):02d}:{int((sleep_h%1)*60):02d}:00+09:00",
                            "stages": [],
                        }
                    ]
                },
            },
            headers=headers,
        )
        c.post(
            "/api/v1/usage-stats",
            json=[
                {
                    "date": d,
                    "category": "SNS",
                    "minutes": random.randint(20, 60),
                    "late_night_minutes": late,
                }
            ],
            headers=headers,
        )
        print(f"  헬스 {d}: {steps}보 / 수면 {sleep_h}h / 야간폰 {late}분")
        time.sleep(0.2)


with httpx.Client(base_url=BASE, timeout=90) as c:
    for acc in ACCOUNTS:
        print(f"\n── {acc['email']} ──")

        c.post(
            "/api/v1/auth/register",
            json={
                "email": acc["email"],
                "password": PASSWORD,
                "nickname": acc["nickname"],
            },
        )
        r = c.post(
            "/api/v1/auth/login", json={"email": acc["email"], "password": PASSWORD}
        )
        if r.status_code != 200:
            print(f"  로그인 실패: {r.status_code}")
            continue
        token = r.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        pets = c.get("/api/v1/pets", headers=headers).json()
        if pets:
            pet_id = pets[0]["id"]
            print(f"  기존 펫: {pet_id}")
        else:
            r = c.post(
                "/api/v1/pets",
                json={
                    "name": acc["pet_name"],
                    "species": "강아지",
                    "breed": "말티즈",
                    "gender": acc["gender"],
                    "caller_name": "보호자",
                    "period": "2019-01-01 ~ 2026-06-01",
                    "memories": [
                        {
                            "keyword": "소중한 추억",
                            "detail": f"{acc['pet_name']}와 함께한 모든 순간이 소중해요.",
                        }
                    ],
                },
                headers=headers,
            )
            if r.status_code != 201:
                print(f"  펫 등록 실패: {r.status_code}")
                continue
            pet_id = r.json()["id"]
            c.patch(f"/api/v1/pets/{pet_id}/memorial", headers=headers)
            print(f"  새 펫 등록: {acc['pet_name']} ({pet_id})")

        if RESET:
            _reset_pet_data(pet_id)

        seed_checkins(c, headers, pet_id)
        seed_health(c, headers, pet_id)
        _insert_missions_mongo(pet_id, MISSIONS_DAYS)

        r = c.get(f"/api/v1/emotions/recovery/{pet_id}", headers=headers)
        d = r.json()
        print(
            f"  → gate={d.get('gate_status')} score={d.get('recovery_pct')} content={d.get('content_unlocked')} allow_1st={d.get('allow_first_person')}"
        )

print("\n완료")
