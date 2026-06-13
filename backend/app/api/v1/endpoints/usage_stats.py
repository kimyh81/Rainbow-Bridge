from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from pymongo import UpdateOne

from app.core.deps import get_current_user
from app.db.mongodb import mongodb

router = APIRouter()


class UsageStatItem(BaseModel):
    date: str
    category: str
    minutes: int
    late_night_minutes: int


@router.post("")
async def save_usage_stats(
    items: List[UsageStatItem],
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["user_id"]
    operations = []

    for item in items:
        operations.append(
            UpdateOne(
                {
                    "userId": user_id,
                    "date": item.date,
                    "category": item.category,
                },
                {
                    "$set": {
                        "minutes": item.minutes,
                        "late_night_minutes": item.late_night_minutes,
                        "updatedAt": datetime.now(timezone.utc),
                    },
                    "$setOnInsert": {
                        "createdAt": datetime.now(timezone.utc),
                    },
                },
                upsert=True,
            )
        )

    if operations:
        await mongodb.db["usage_stats"].bulk_write(operations)

    return {"status": "ok", "saved": len(operations)}
