import os
import shutil
from datetime import datetime, timezone

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import HTTPException, UploadFile

from app.db.mongodb import mongodb
from app.schemas.pet import PetCreate, PetPhotoResponse, PetResponse, PetUpdate


def _to_object_id(pet_id: str) -> ObjectId:
    try:
        return ObjectId(pet_id)
    except (InvalidId, Exception):
        raise HTTPException(status_code=404, detail="반려동물 정보를 찾을 수 없습니다.")


_UPLOAD_DIR = "uploads/pets"


def _collection():
    return mongodb.db["pets"]


def _normalize_memories(memories: list | None) -> list | None:
    if not memories:
        return memories
    result = []
    for m in memories:
        if isinstance(m, str):
            result.append({"keyword": m, "detail": ""})
        else:
            result.append(m)
    return result


async def create_pet(data: PetCreate, user_id: int) -> PetResponse:
    doc = data.model_dump()
    doc["user_id"] = user_id
    doc["memorial_mode"] = False
    doc["created_at"] = datetime.now(timezone.utc)

    result = await _collection().insert_one(doc)
    doc["id"] = str(result.inserted_id)
    return PetResponse(**doc)


async def get_pet(pet_id: str, user_id: int | None = None) -> PetResponse | None:
    query: dict = {"_id": _to_object_id(pet_id)}
    if user_id is not None:
        query["user_id"] = user_id
    doc = await _collection().find_one(query)
    if not doc:
        return None
    doc["id"] = str(doc.pop("_id"))
    doc["memories"] = _normalize_memories(doc.get("memories"))
    return PetResponse(**doc)


async def get_pets_by_user(user_id: int) -> list[PetResponse]:
    cursor = _collection().find({"user_id": user_id}).sort("created_at", -1)
    pets = []
    async for doc in cursor:
        doc["id"] = str(doc.pop("_id"))
        doc["memories"] = _normalize_memories(doc.get("memories"))
        pets.append(PetResponse(**doc))
    return pets


async def upload_pet_photo(pet_id: str, file: UploadFile) -> PetPhotoResponse | None:
    doc = await _collection().find_one({"_id": _to_object_id(pet_id)})
    if not doc:
        return None

    os.makedirs(_UPLOAD_DIR, exist_ok=True)
    ext = os.path.splitext(file.filename or "photo.jpg")[1] or ".jpg"
    filename = f"{pet_id}{ext}"
    filepath = os.path.join(_UPLOAD_DIR, filename)

    with open(filepath, "wb") as f:
        shutil.copyfileobj(file.file, f)

    photo_url = f"/uploads/pets/{filename}"
    await _collection().update_one(
        {"_id": _to_object_id(pet_id)}, {"$set": {"photo_url": photo_url}}
    )
    return PetPhotoResponse(id=pet_id, photo_url=photo_url)


async def update_pet(pet_id: str, data: PetUpdate, user_id: int) -> PetResponse | None:
    update_fields = {k: v for k, v in data.model_dump().items() if v is not None}
    if "memories" in update_fields:
        update_fields["memories"] = _normalize_memories(update_fields["memories"])
    if not update_fields:
        return await get_pet(pet_id, user_id=user_id)
    doc = await _collection().find_one_and_update(
        {"_id": _to_object_id(pet_id), "user_id": user_id},
        {"$set": update_fields},
        return_document=True,
    )
    if not doc:
        return None
    doc["id"] = str(doc.pop("_id"))
    doc["memories"] = _normalize_memories(doc.get("memories"))
    return PetResponse(**doc)


async def set_memorial_mode(pet_id: str) -> PetResponse | None:
    doc = await _collection().find_one_and_update(
        {"_id": _to_object_id(pet_id)},
        {"$set": {"memorial_mode": True}},
        return_document=True,
    )
    if not doc:
        return None
    doc["id"] = str(doc.pop("_id"))
    return PetResponse(**doc)


async def update_pet(pet_id: str, data) -> PetResponse | None:
    update_fields = {k: v for k, v in data.model_dump().items() if v is not None}
    if not update_fields:
        doc = await _collection().find_one({"_id": _to_object_id(pet_id)})
    else:
        if "memories" in update_fields:
            update_fields["memories"] = _normalize_memories(update_fields["memories"])
        doc = await _collection().find_one_and_update(
            {"_id": _to_object_id(pet_id)},
            {"$set": update_fields},
            return_document=True,
        )
    if not doc:
        return None
    doc["id"] = str(doc.pop("_id"))
    doc["memories"] = _normalize_memories(doc.get("memories"))
    return PetResponse(**doc)
