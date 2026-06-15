# 핸드오프 — TTS 터널 URL 자동 반영 (→ 김윤한 백엔드)

> 작성: 정환주 · 대상: `backend/app/services/tts.py` + 신규 등록 엔드포인트(김윤한)
> 목적: cloudflared **quick tunnel URL이 재부팅·재시작마다 바뀌는데** NCP `.env` 를 매번 수동
> 갱신해야 해서 팀 진도가 막히던 문제 해결. **백엔드가 최신 URL 을 자동으로 받게** 한다.

---

## 문제

```
앱 → NCP 백엔드(.env TTS_SERVER_URL) → 터널 URL → 정환주 GPU(Qwen3)
                  ▲ 여기가 옛 URL이면 죽은 터널 호출 → 503 → 구글 폴백(qwen3 안 나옴)
```

cloudflared `tunnel --url localhost:8003` = quick tunnel → 재시작마다 새 `*.trycloudflare.com`.
고정 도메인 안 씀(팀이 cloudflared 유지 합의). 그래서 **누군가 NCP 에 새 URL 을 계속 알려줘야** 함.

## 해결 — watchdog 이 push, 백엔드는 동적 사용

```
[정환주 PC] watchdog(레포 밖 ps1)
   ├ cloudflared 죽으면 자동 재시작
   ├ /quicktunnel 로 현재 URL 조회 + /tts/health(model_ready) 검증
   └ URL 바뀌면 ──POST /api/v1/tts/register-url (시크릿)──▶ [NCP 백엔드]
                                                              └ Redis 저장 → tts.py 가 사용
```

- watchdog(정환주 운영)은 **검증된 URL 만** 보냄. 백엔드는 받은 URL 을 저장해서 쓰면 됨.
- `.env TTS_SERVER_URL` 은 **폴백**으로 유지(등록값 없을 때).

---

## 백엔드 작업 (김윤한) — 2가지

### ① 등록 엔드포인트 신규: `POST /api/v1/tts/register-url`

> Redis 는 **기존 `get_redis()`**(`app/db/redis_client.py`, `aioredis.Redis`, `decode_responses=True`)를
> 그대로 씀 — `.get/.set` 직접 호출(별도 래퍼 불필요, get 결과는 str).

```python
import os
from urllib.parse import urlparse
import httpx
from fastapi import Header, HTTPException
from pydantic import BaseModel
from app.db.redis_client import get_redis

_TTS_URL_KEY = "tts:server_url"
_TTS_URL_TTL = 300  # 초 — watchdog heartbeat(120s)보다 길게. watchdog 죽으면 만료→ .env 폴백 자동 복원

class TtsUrlIn(BaseModel):
    url: str  # 예: "https://xxx.trycloudflare.com/tts" (base + /tts)

@router.post("/register-url")
async def register_tts_url(body: TtsUrlIn, x_tts_secret: str = Header(...)):
    secret = os.environ.get("TTS_REGISTER_SECRET")
    if not secret:
        raise HTTPException(503, "TTS_REGISTER_SECRET 미설정")  # 설정 누락 → 503(403과 구분)
    if x_tts_secret != secret:
        raise HTTPException(403, "bad secret")
    # 화이트리스트 — https + *.trycloudflare.com 만(시크릿 유출 시 내부망 SSRF·임의 목적지 차단)
    u = urlparse(body.url)
    if u.scheme != "https" or not (u.hostname or "").endswith(".trycloudflare.com"):
        raise HTTPException(400, "허용되지 않은 URL")
    # 저장 전 백엔드도 health 재검증(죽은 URL 오염 차단). body.url=base+/tts → /health 는 /tts/health
    async with httpx.AsyncClient(timeout=8) as c:
        h = await c.get(f"{body.url.rstrip('/')}/health")
        if h.json().get("model_ready") is not True:
            raise HTTPException(400, "health 실패")
    await get_redis().set(_TTS_URL_KEY, body.url, ex=_TTS_URL_TTL)  # ★TTL 필수
    return {"ok": True, "url": body.url}
```

⚠️ **TTL(`ex=300`)이 핵심.** TTL 없이 저장하면, 정환주 PC 재부팅·watchdog 미기동 시 **죽은 URL 이
Redis 에 영구히 남아** 백엔드가 매번 죽은 터널로 가서 60초 타임아웃 후에야 폴백(매 TTS 60초 지연).
TTL 을 주면 watchdog 이 살아있을 땐 계속 갱신, 죽으면 만료 → `.env` 폴백으로 **자동 복원**.

### ② `tts.py` — Redis URL 우선, `.env` 폴백

현재 `backend/app/services/tts.py:66`:
```python
tts_server_url = os.environ.get("TTS_SERVER_URL", "").strip()
```
→ 아래로 (`get_redis` import 추가):
```python
from app.db.redis_client import get_redis
...
dyn = await get_redis().get("tts:server_url")  # watchdog 등록 최신 URL(decode_responses=True → str|None)
tts_server_url = (dyn or os.environ.get("TTS_SERVER_URL", "")).strip()
```
- `dyn` 있으면 그걸, 없으면(미등록/TTL 만료) 기존 `.env` 폴백 → **하위호환**(등록 전엔 지금과 동일).
- `generate_tts` 가 이미 `async def`(요청당 호출)라 `await get_redis().get(...)` 그대로 OK.
- `dyn` 형식은 `.env` 와 동일 `https://xxx.trycloudflare.com/tts`(접미사 `/tts`) → 기존 `f"{server_url.rstrip('/')}/synthesize"` 로직 무수정.

### 시크릿 공유
- 백엔드 `.env`: `TTS_REGISTER_SECRET=<랜덤 긴 문자열>`
- 정환주 watchdog 도 같은 값 사용(정환주 PC 로컬, 레포에 커밋 안 함).
- 값 1개만 둘이 맞추면 됨. 합의 후 알려주세요.

---

## 정환주 쪽 (준비됨) — 윤한 작업 불필요

- watchdog: `C:\Rainbow_Bridge\tts_url_watchdog.ps1`(레포 밖, git 무관).
- 30초마다: **8003 터널 cloudflared** 생존·재시작(좀비 연속실패 시 강제 kill+즉시 재기동, CommandLine 으로 8003 터널만 식별해 타 cloudflared 동반사살 방지) → `/quicktunnel` URL → `/tts/health`(model_ready) 검증 → 바뀌면(또는 120s heartbeat마다) 위 엔드포인트로 POST.
- **heartbeat 재등록**(4루프=120s)으로 백엔드 Redis TTL(300s)을 갱신 유지 → watchdog 살아있는 한 등록값 안 만료.
- **supervisor**: watchdog 자체가 죽으면 stale → Task Scheduler "실패 시 재시작" 또는 자동시작 스크립트로 기동 필요. (단 백엔드 TTL 덕에 watchdog 죽어도 5분 뒤 `.env` 폴백 자동 복원이라 치명적이진 않음 — 안전망 이중화)
- **엔드포인트 경로(`/api/v1/tts/register-url`)·시크릿만 합의되면** watchdog 상수 2개(`$BACKEND_REGISTER`·`$SECRET`)만 맞추면 바로 작동.

---

## 정리

| 누가 | 무엇 | 상태 |
|------|------|------|
| 김윤한 | `POST /tts/register-url`(시크릿+`*.trycloudflare.com` 화이트리스트+health 재검증+**TTL 300s**) + `tts.py` `get_redis().get` 우선·`.env` 폴백 + `.env` 시크릿 | ⬜ 이 문서대로 |
| 정환주 | watchdog(검증·재시작·heartbeat push) + supervisor 등록 | ✅ 준비됨(경로·시크릿 합의 후 가동) |

**이중 안전망:** ① watchdog 살아있음 → 최신 URL 항상 등록(TTL 갱신). ② watchdog 죽음 → TTL 만료 → `.env` 폴백 복원. 어느 쪽도 "죽은 URL 영구 고정" 안 됨.

→ 이러면 정환주 PC 재부팅하든 터널이 죽든, watchdog 이 새 URL 을 검증해서 백엔드에 자동 등록 →
**앱에서 항상 Qwen3 음성**. 더이상 수동 `.env` 갱신·URL 물어보기 없음.

---

## 진단 — `status=None / [Errno -2] Name or service not known`

이 에러 = **DNS resolve 실패** = 백엔드가 **죽은(옛) 터널 URL** 을 조회한 것. (호스트 자체가 사라져서
이름 해석이 안 됨 — 휘발성 quick tunnel 이 재시작돼 옛 `*.trycloudflare.com` 이 소멸한 전형적 증상.)
**이 자동화가 바로 그걸 해결**한다 — watchdog 이 최신 URL 을 등록해 백엔드가 항상 살아있는 주소를 봄.

### 모세종 체크리스트 → watchdog 자동 점검 매핑

| 모세종 체크리스트 | watchdog 단계(로그 prefix) | 자동 처리 |
|-------------------|----------------------------|-----------|
| GPU 서버 켜졌나 / FastAPI 실행 중인가 | `[GPU]` localhost:8003 `/tts/health` model_ready | 죽으면 진단 로그(uvicorn 확인 안내) |
| 외부에서 접근 가능한가 | `[외부]` 터널 URL `/tts/health` | 실패 시 터널/방화벽 의심 로그 |
| 터널 살아있나 | `[터널]` cloudflared 생존·`/quicktunnel` | 죽으면 자동 재시작 |
| **TTS_SERVER_URL 맞나** | `[등록]` 최신 URL 백엔드 등록 | **자동 일치** (수동 갱신 불필요) |

→ watchdog 가동 후엔 이 4개를 30초마다 자동 점검. 문제 단계가 `logs/tts_url_watchdog.log` 에
prefix(`[GPU]`/`[터널]`/`[외부]`/`[등록]`)로 찍혀 **어디서 막혔는지 즉시** 보인다.

### 백엔드 진단 로그 (윤한, 선택) — 어느 URL 을 쳤는지 남기기

`Name or service not known` 이 떠도 지금은 **어느 URL** 을 친 건지 로그에 안 보임. `_qwen3_remote`
실패 분기에 한 줄 추가하면 즉시 진단됨:
```python
except httpx.HTTPError as e:
    logger.warning(f"TTS 원격 실패 — url={tts_server_url} (출처:{'redis' if dyn else 'env'}) err={e}")
    return await _google_tts_fallback(data)   # 기존 폴백 유지
```
→ "옛 env URL 이었네" / "redis 값이 죽었네" 를 로그 한 줄로 구분. (status=None 디버깅 종결)

---

질문은 정환주에게.
