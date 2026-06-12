from fastapi import APIRouter, Depends
from pymongo import UpdateOne
from datetime import datetime, timezone
from typing import List
from pydantic import BaseModel

from app.core.deps import get_current_user
from app.db.mongodb import mongodb

router = APIRouter()


class UsageStatItem(BaseModel):
    date: str
    package: str
    minutes: int
    late_night_minutes: int


@router.post("")
async def save_usage_stats(
    items: List[UsageStatItem],
    current_user: dict = Depends(get_current_user),
):
    user_id = str(current_user["_id"])
    operations = []

    for item in items:
        operations.append(
            UpdateOne(
                {
                    "userId": user_id,
                    "date": item.date,
                    "package": item.package,
                },
                {
                    "$set": {
                        "minutes": item.minutes,
                        "late_night_minutes": item.late_night_minutes,
                        "createdAt": datetime.now(timezone.utc),
                    }
                },
                upsert=True,
            )
        )

    if operations:
        await mongodb.db["usage_stats"].bulk_write(operations)

    return {"status": "ok", "saved": len(operations)}
