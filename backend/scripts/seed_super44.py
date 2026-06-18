"""super44@rainbow.dev 계정 생성 + gate open (MongoDB 직접 삽입)"""

import asyncio
import httpx
from datetime import datetime, timedelta, timezone
from motor.motor_asyncio import AsyncIOMotorClient

BASE = "http://localhost:8000"
MONGO_URI = "mongodb://rainbow_mongo:27017"
DB_NAME = "rainbow_bridge"

EMAIL = "super44@rainbow.dev"
PW = "super4444"
PET_NAME = "몽실이"


async def main():
    # 1. 회원가입 + 펫 생성 (HTTP)
    with httpx.Client(base_url=BASE, timeout=30) as c:
        r = c.post(
            "/api/v1/auth/register",
            json={
                "email": EMAIL,
                "password": PW,
                "name": "시연계정44",
                "nickname": "몽실이보호자",
            },
        )
        print("register:", r.status_code)

        r = c.post("/api/v1/auth/login", json={"email": EMAIL, "password": PW})
        if r.status_code != 200:
            print("로그인 실패:", r.text)
            return
        token = r.json()["access_token"]
        h = {"Authorization": f"Bearer {token}"}
        print("로그인 성공")

        r = c.post(
            "/api/v1/pets",
            json={
                "name": PET_NAME,
                "species": "강아지",
                "period": "2020-01-01 ~ 2026-06-01",
                "caller_name": "보호자",
                "gender": "남아",
            },
            headers=h,
        )
        if r.status_code == 201:
            pet_id = r.json().get("id") or r.json().get("_id")
            print("펫 생성:", pet_id)
        else:
            pets = c.get("/api/v1/pets", headers=h).json()
            pet_id = pets[0]["id"] if pets else None
            print("기존 펫 사용:", pet_id)

    if not pet_id:
        print("펫 없음. 종료.")
        return

    # 2. MongoDB 직접 삽입 (감정 API 타임아웃 우회)
    client = AsyncIOMotorClient(MONGO_URI)
    db = client[DB_NAME]

    user = await db["users"].find_one({"email": EMAIL})
    user_id = user.get("id") if user else None

    count = await db["emotions"].count_documents({"pet_id": pet_id})
    need = max(0, 14 - count)
    if need > 0:
        now = datetime.now(timezone.utc)
        docs = [
            {
                "pet_id": pet_id,
                "user_id": user_id,
                "score": 9,
                "note": "",
                "risk_level": 0,
                "created_at": now - timedelta(hours=i),
            }
            for i in range(need)
        ]
        await db["emotions"].insert_many(docs)
        print(f"체크인 {need}개 직접 삽입 완료")
    else:
        print(f"체크인 이미 {count}개 있음")

    client.close()
    print(f"\n완료! {EMAIL} / {PW} / 펫: {PET_NAME}")
    print("앱에서 로그인 후 gate=open 확인하세요.")


asyncio.run(main())
