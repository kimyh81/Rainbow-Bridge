"""super44 gate 상태 확인 + 부족하면 MongoDB 직접 삽입으로 체크인 보충"""

import asyncio
from datetime import datetime, timedelta, timezone

from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URI = "mongodb://rainbow_mongo:27017"
DB_NAME = "rainbow_bridge"

EMAIL = "super44@rainbow.dev"


async def main():
    client = AsyncIOMotorClient(MONGO_URI)
    db = client[DB_NAME]

    # 유저 확인
    user = await db["users"].find_one({"email": EMAIL})
    if not user:
        print("계정 없음 — 먼저 register 필요")
        return
    user_id = user["id"] if "id" in user else user["_id"]
    print(f"유저: {user_id} ({EMAIL})")

    # 펫 확인
    pet = await db["pets"].find_one({"user_id": user_id})
    if not pet:
        print("펫 없음")
        return
    pet_id = str(pet["_id"]) if "_id" in pet else str(pet["id"])
    print(f"펫: {pet_id} ({pet.get('name')})")

    # 기존 체크인 수 확인
    count = await db["emotions"].count_documents({"pet_id": pet_id})
    print(f"현재 체크인 수: {count}")

    # 14개 미만이면 MongoDB에 직접 삽입
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

    print("gate 확인 완료 — 이제 앱에서 로그인해보세요!")
    client.close()


asyncio.run(main())
