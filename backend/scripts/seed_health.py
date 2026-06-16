"""데모 계정 건강 데이터 시드 스크립트 (아이폰 대응)

삼성헬스 연동이 불가한 환경(아이폰 등)에서 health_logs를 직접 MongoDB에 삽입합니다.
수면 변화 차트(report 화면) + 회복점수 생활패턴 축에 반영됩니다.

실행:
  cd backend
  MONGO_URI=mongodb://localhost:27017 MONGO_DB_NAME=rainbow_bridge \\
    python3 scripts/seed_health.py
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone

import httpx
from pymongo import MongoClient, UpdateOne

BASE = "https://rainbow-bridge.duckdns.org"
PASSWORD = "js1234"

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB = os.getenv("MONGO_DB_NAME", "rainbow_bridge")

ACCOUNTS = [
    "demo00@demo.com",
    "demo01@demo.com",
    "demo02@demo.com",
    "demo03@demo.com",
    "demo04@demo.com",
    "demo05@demo.com",
]

# 계정별 최근 N일치 데이터 설정
HEALTH_CONFIG = {
    "demo00@demo.com": {"days": 0},
    "demo01@demo.com": {"days": 3},
    "demo02@demo.com": {"days": 5},
    "demo03@demo.com": {"days": 5},
    "demo04@demo.com": {"days": 7},
    "demo05@demo.com": {"days": 0},
}

# 날짜별 수면/걸음 패턴 (회복 흐름을 보여주도록 상승세로)
DAILY_PATTERN = [
    {"sleep_hours": 5.5, "steps": 3200},
    {"sleep_hours": 5.8, "steps": 4100},
    {"sleep_hours": 6.0, "steps": 5500},
    {"sleep_hours": 6.3, "steps": 6200},
    {"sleep_hours": 6.5, "steps": 7000},
    {"sleep_hours": 7.0, "steps": 7800},
    {"sleep_hours": 7.2, "steps": 8500},
]


def get_pet_ids() -> dict[str, str]:
    """API 로그인 → pet_id 수집."""
    pet_ids: dict[str, str] = {}
    with httpx.Client(base_url=BASE, timeout=30) as c:
        for email in ACCOUNTS:
            r = c.post(
                "/api/v1/auth/login", json={"email": email, "password": PASSWORD}
            )
            if r.status_code != 200:
                print(f"  {email} 로그인 실패: {r.status_code}")
                continue
            token = r.json()["access_token"]
            pets = c.get(
                "/api/v1/pets", headers={"Authorization": f"Bearer {token}"}
            ).json()
            if not pets:
                print(f"  {email} 펫 없음")
                continue
            pet_ids[email] = pets[0]["id"]
            print(f"  {email} → pet_id={pets[0]['id']}")
    return pet_ids


def seed_health(pet_ids: dict[str, str]) -> None:
    client = MongoClient(MONGO_URI)
    db = client[MONGO_DB]
    col = db["health_logs"]

    ops = []
    today = datetime.now(timezone.utc).date()

    for email, pet_id in pet_ids.items():
        cfg = HEALTH_CONFIG.get(email, {"days": 0})
        days = cfg["days"]
        if days == 0:
            continue

        # 오늘부터 N일 전까지 역순 삽입 (DAILY_PATTERN 마지막이 오늘에 가까움)
        pattern_slice = DAILY_PATTERN[-days:]
        for i, pattern in enumerate(pattern_slice):
            date = today - timedelta(days=(days - 1 - i))
            date_str = date.isoformat()
            ops.append(
                UpdateOne(
                    {"pet_id": pet_id, "date": date_str},
                    {
                        "$set": {
                            "sleep_hours": pattern["sleep_hours"],
                            "steps": pattern["steps"],
                            "synced_at": datetime.now(timezone.utc),
                        }
                    },
                    upsert=True,
                )
            )
            print(
                f"    {email} {date_str}: sleep={pattern['sleep_hours']}h steps={pattern['steps']}"
            )

    if ops:
        result = col.bulk_write(ops)
        print(
            f"\n삽입/업데이트: {result.upserted_count}건 신규, {result.modified_count}건 갱신"
        )
    else:
        print("삽입할 데이터 없음")

    client.close()


if __name__ == "__main__":
    print("=== 헬스 데이터 시드 시작 ===")
    print("\n1. 펫 ID 수집 중...")
    pet_ids = get_pet_ids()
    if not pet_ids:
        print("펫 ID를 가져올 수 없어요. 서버 연결 상태를 확인하세요.")
        sys.exit(1)

    print(f"\n2. MongoDB({MONGO_URI}/{MONGO_DB}) health_logs 삽입 중...")
    seed_health(pet_ids)
    print("\n=== 완료 ===")
