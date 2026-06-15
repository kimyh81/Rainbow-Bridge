from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.core.deps import get_current_user
from app.schemas.pet import PetCreate, PetPhotoResponse, PetResponse, PetUpdate
from app.services.pet import (
    create_pet,
    get_pet,
    set_memorial_mode,
    update_pet,
    upload_pet_photo,
)

router = APIRouter()


@router.post("", response_model=PetResponse, status_code=201)
async def register_pet(body: PetCreate, user: dict = Depends(get_current_user)):
    return await create_pet(body, user_id=user["user_id"])


@router.get("", response_model=list[PetResponse])
async def list_pets(user: dict = Depends(get_current_user)):
    from app.services.pet import get_pets_by_user

    return await get_pets_by_user(user["user_id"])


@router.get("/{pet_id}", response_model=PetResponse)
async def read_pet(pet_id: str, user: dict = Depends(get_current_user)):
    pet = await get_pet(pet_id, user_id=user["user_id"])
    if not pet:
        raise HTTPException(status_code=404, detail="반려동물 정보를 찾을 수 없습니다.")
    return pet


@router.patch("/{pet_id}", response_model=PetResponse)
async def update_pet_info(
    pet_id: str, body: PetUpdate, user: dict = Depends(get_current_user)
):
    pet = await update_pet(pet_id, body, user_id=user["user_id"])
    if not pet:
        raise HTTPException(status_code=404, detail="반려동물 정보를 찾을 수 없습니다.")
    return pet


@router.post("/{pet_id}/photo", response_model=PetPhotoResponse)
async def upload_photo(
    pet_id: str, file: UploadFile = File(...), user: dict = Depends(get_current_user)
):
    if not await get_pet(pet_id, user_id=user["user_id"]):
        raise HTTPException(status_code=404, detail="반려동물 정보를 찾을 수 없습니다.")
    result = await upload_pet_photo(pet_id, file)
    if not result:
        raise HTTPException(status_code=404, detail="반려동물 정보를 찾을 수 없습니다.")
    return result


@router.patch("/{pet_id}", response_model=PetResponse)
async def update_pet_info(
    pet_id: str, body: PetUpdate, user: dict = Depends(get_current_user)
):
    if not await get_pet(pet_id, user_id=user["user_id"]):
        raise HTTPException(status_code=404, detail="반려동물 정보를 찾을 수 없습니다.")
    pet = await update_pet(pet_id, body)
    if not pet:
        raise HTTPException(status_code=404, detail="반려동물 정보를 찾을 수 없습니다.")
    return pet


@router.patch("/{pet_id}/memorial", response_model=PetResponse)
async def switch_memorial(pet_id: str, user: dict = Depends(get_current_user)):
    if not await get_pet(pet_id, user_id=user["user_id"]):
        raise HTTPException(status_code=404, detail="반려동물 정보를 찾을 수 없습니다.")
    pet = await set_memorial_mode(pet_id)
    if not pet:
        raise HTTPException(status_code=404, detail="반려동물 정보를 찾을 수 없습니다.")
    return pet
