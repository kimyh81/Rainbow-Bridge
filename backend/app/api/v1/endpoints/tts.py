import os
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from app.core.deps import get_current_user
from app.db.redis_client import get_redis
from app.schemas.tts import TtsCreate, TtsResponse
from app.services.tts import generate_tts

router = APIRouter()

_TTS_URL_KEY = "tts:server_url"
_TTS_URL_TTL = 300


class TtsUrlIn(BaseModel):
    url: str


@router.post("", response_model=TtsResponse, status_code=201)
async def synthesize_tts(body: TtsCreate, user: dict = Depends(get_current_user)):
    return await generate_tts(body)


@router.post("/register-url")
async def register_tts_url(body: TtsUrlIn, x_tts_secret: str = Header(...)):
    secret = os.environ.get("TTS_REGISTER_SECRET")
    if not secret:
        raise HTTPException(503, "TTS_REGISTER_SECRET 미설정")
    if x_tts_secret != secret:
        raise HTTPException(403, "bad secret")
    u = urlparse(body.url)
    if u.scheme != "https" or not (u.hostname or "").endswith(".trycloudflare.com"):
        raise HTTPException(400, "허용되지 않은 URL")
    async with httpx.AsyncClient(timeout=8) as c:
        h = await c.get(f"{body.url.rstrip('/')}/health")
        if h.json().get("model_ready") is not True:
            raise HTTPException(400, "health 실패")
    await get_redis().set(_TTS_URL_KEY, body.url, ex=_TTS_URL_TTL)
    return {"ok": True, "url": body.url}
