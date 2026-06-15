"""
발표용 데모 계정 6개 생성 스크립트
각 계정은 게이트 상태(락/언락)가 다르게 설정됨

실행: python backend/scripts/seed_demo_accounts.py
"""

import asyncio
import httpx
from datetime import datetime, timezone, timedelta
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId

BASE_URL = "http://localhost:8000"
MONGO_URL = "mongodb://localhost:27017"
DB_NAME = "rainbow_bridge"

# ── 데모 계정 정의 ───────────────────────────────────────────────
ACCOUNTS = [
    {
        "label": "demo1 — 완전 락 (신규, 체크인 없음)",
        "email": "demo1@test.com",
        "password": "demo1234",
        "nickname": "데모1",
        "pet": {
            "name": "하늘이",
            "species": "강아지",
            "caller_name": "엄마",
            "gender": "남아",
        },
        "checkins": [],  # 0개
        "memorial_mode": False,
    },
    {
        "label": "demo2 — 진행중 락 (체크인 1개, 개수 부족)",
        "email": "demo2@test.com",
        "password": "demo1234",
        "nickname": "데모2",
        "pet": {
            "name": "별이",
            "species": "강아지",
            "caller_name": "아빠",
            "gender": "여아",
        },
        "checkins": [{"score": 7, "risk_level": 0}],  # 1개
        "memorial_mode": True,
    },
    {
        "label": "demo3 — score 미달 락 (체크인 3개, 평균 score 낮음)",
        "email": "demo3@test.com",
        "password": "demo1234",
        "nickname": "데모3",
        "pet": {
            "name": "콩이",
            "species": "고양이",
            "caller_name": "누나",
            "gender": "남아",
        },
        "checkins": [
            {"score": 3, "risk_level": 0},
            {"score": 2, "risk_level": 0},
            {"score": 3, "risk_level": 0},
        ],  # 3개, 평균 2.7 → score 미달
        "memorial_mode": True,
    },
    {
        "label": "demo4 — risk 위험 락 (체크인 5개, score 높지만 risk=2)",
        "email": "demo4@test.com",
        "password": "demo1234",
        "nickname": "데모4",
        "pet": {
            "name": "달이",
            "species": "강아지",
            "caller_name": "엄마",
            "gender": "여아",
        },
        "checkins": [
            {"score": 8, "risk_level": 2},  # 최근 risk=2 → 락
            {"score": 8, "risk_level": 0},
            {"score": 9, "risk_level": 0},
            {"score": 7, "risk_level": 0},
            {"score": 8, "risk_level": 0},
        ],
        "memorial_mode": True,
    },
    {
        "label": "demo5 — 추모 컨텐츠만 언락 (risk=1 있어서 1인칭 락)",
        "email": "demo5@test.com",
        "password": "demo1234",
        "nickname": "데모5",
        "pet": {
            "name": "봄이",
            "species": "고양이",
            "caller_name": "오빠",
            "gender": "여아",
        },
        "checkins": [
            {"score": 7, "risk_level": 1},  # risk=1 있음 → 1인칭 락
            {"score": 8, "risk_level": 0},
            {"score": 7, "risk_level": 0},
            {"score": 6, "risk_level": 0},
            {"score": 8, "risk_level": 0},
        ],  # 평균 7.2 → content_unlocked=true, 1인칭=false
        "memorial_mode": True,
    },
    {
        "label": "demo6 — 완전 언락 (1인칭 편지까지 전부 열림)",
        "email": "demo6@test.com",
        "password": "demo1234",
        "nickname": "데모6",
        "pet": {
            "name": "구름이",
            "species": "강아지",
            "caller_name": "엄마",
            "gender": "남아",
        },
        "checkins": [
            {"score": 9, "risk_level": 0},
            {"score": 9, "risk_level": 0},
            {"score": 8, "risk_level": 0},
            {"score": 9, "risk_level": 0},
            {"score": 8, "risk_level": 0},
        ],  # 전체 risk=0 → 1인칭까지 완전 언락
        "memorial_mode": True,
    },
]


async def create_account(client: httpx.AsyncClient, acc: dict) -> str | None:
    """회원가입 → user_id 반환."""
    r = await client.post(
        f"{BASE_URL}/api/v1/auth/register",
        json={
            "email": acc["email"],
            "password": acc["password"],
            "nickname": acc["nickname"],
        },
    )
    if r.status_code not in (200, 201):
        print(f"  ⚠️  회원가입 실패 ({r.status_code}): {r.text[:80]}")
        return None
    print(f"  ✅ 회원가입 완료: {acc['email']}")
    return r.json().get("id")


async def login(client: httpx.AsyncClient, acc: dict) -> str | None:
    """로그인 → JWT 토큰 반환."""
    r = await client.post(
        f"{BASE_URL}/api/v1/auth/login",
        json={
            "email": acc["email"],
            "password": acc["password"],
        },
    )
    if r.status_code != 200:
        print(f"  ⚠️  로그인 실패: {r.text[:80]}")
        return None
    return r.json().get("access_token")


async def create_pet(client: httpx.AsyncClient, token: str, acc: dict) -> str | None:
    """반려동물 등록 → pet_id 반환."""
    r = await client.post(
        f"{BASE_URL}/api/v1/pets",
        json={
            "name": acc["pet"]["name"],
            "species": acc["pet"]["species"],
            "caller_name": acc["pet"]["caller_name"],
            "gender": acc["pet"]["gender"],
            "period": "3년",
            "memories": [f"{acc['pet']['name']}와 함께한 소중한 기억들"],
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    if r.status_code not in (200, 201):
        print(f"  ⚠️  펫 등록 실패: {r.text[:80]}")
        return None
    pet_id = r.json().get("id")
    print(f"  ✅ 펫 등록: {acc['pet']['name']} (id={pet_id})")
    return pet_id


async def seed_checkins(db, pet_id: str, checkins: list, memorial_mode: bool):
    """체크인 MongoDB 직접 삽입 + memorial_mode 설정."""
    if checkins:
        now = datetime.now(timezone.utc)
        docs = []
        for i, c in enumerate(checkins):
            docs.append(
                {
                    "pet_id": pet_id,
                    "score": c["score"],
                    "note": "",
                    "risk_level": c["risk_level"],
                    "created_at": now - timedelta(hours=i),
                }
            )
        await db["emotions"].insert_many(docs)
        print(f"  ✅ 체크인 {len(docs)}개 삽입")

    if memorial_mode:
        await db["pets"].update_one(
            {"_id": ObjectId(pet_id)},
            {"$set": {"memorial_mode": True}},
        )
        print("  ✅ memorial_mode=true 설정")


async def main():
    mongo = AsyncIOMotorClient(MONGO_URL)
    db = mongo[DB_NAME]

    async with httpx.AsyncClient(timeout=30) as client:
        for acc in ACCOUNTS:
            print(f"\n{'='*60}")
            print(f"📋 {acc['label']}")
            print(f"   {acc['email']} / {acc['password']}")

            await create_account(client, acc)
            token = await login(client, acc)
            if not token:
                continue

            pet_id = await create_pet(client, token, acc)
            if not pet_id:
                continue

            await seed_checkins(db, pet_id, acc["checkins"], acc["memorial_mode"])

    mongo.close()
    print(f"\n{'='*60}")
    print("✅ 데모 계정 생성 완료!")
    print()
    print("계정 요약:")
    for acc in ACCOUNTS:
        print(
            f"  {acc['email']} / {acc['password']}  →  {acc['label'].split('—')[1].strip()}"
        )


if __name__ == "__main__":
    asyncio.run(main())
