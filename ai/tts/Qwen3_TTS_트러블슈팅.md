# 🌈 Rainbow Bridge — Qwen3 TTS 트러블슈팅 문서

> 작성일: 2026-06-15
> 대상: 정환주(GPU TTS 서버) · 윤한/세종(NCP 백엔드) · 민경(프론트)
> 범위: Qwen3 GPU TTS 서버를 NCP 백엔드와 연동하며 겪은 전체 문제·원인·해결 기록

---

## 0. 요약 (TL;DR)

**핵심 증상**
- TTS가 Qwen3 대신 **Google/gTTS 폴백**으로 나옴 (저음질, 3인칭 기본)
- async 합성이 `degraded(GPU 정체)`로 반복 실패
- cloudflared 터널 URL이 재시작마다 바뀌어 등록이 자꾸 죽음

**근본 원인 (3가지)**
1. **Redis `tts:server_url`이 비거나 stale** → 백엔드가 Qwen3를 건너뛰고 WaveSpeed/Google 폴백
2. **`_degraded` 래치** → 합성이 300초 초과(GPU 정체)하면 켜지고, 재시작 전까지 모든 요청을 503/error로 거절
3. **cloudflared quick tunnel URL이 재시작마다 변경** + **GitHub push ≠ NCP 배포** 혼선

**결론**
- 환주 영역: GPU 서버 healthy 유지 / degraded 시 재시작 / URL 재등록 / VRAM 여유 확보
- 백엔드 영역(윤한·세종): Redis TTL 늘리기 / 폴백 일관성 / WaveSpeed payload / NCP 실제 배포
- **양자화는 불가** (RTX 5060 sm_120 + 커스텀 qwen_tts 라이브러리)
- **근본 해결 = Named Tunnel(고정 URL) + Redis TTL 제거**

---

## 1. 시스템 구조

```
[프론트(앱)]
     │  POST /api/v1/tts
     ▼
[NCP 백엔드] rainbow-bridge.duckdns.org (Docker, 포트 8000)
     │  Redis tts:server_url 조회
     │  ① if URL 있음 → Qwen3 호출
     │  ② 실패/없음 → WaveSpeed → Google → gTTS 폴백
     ▼  (HTTP, cloudflared 터널 경유)
[환주 GPU 서버] Windows · RTX 5060 8GB · 포트 8002
     - start_tts.bat (conda qwen3-tts → server.py)
     - cloudflared quick tunnel → https://[랜덤].trycloudflare.com
     - /api/v1/tts/register-url 로 현재 URL을 백엔드에 등록
```

**폴백 체인 (백엔드 `generate_tts`)**
```
Qwen3 (self-host, 등록 URL) → WaveSpeedAI → Google Cloud TTS → gTTS
```

**TTS 엔드포인트 (환주 server.py)**
| 경로 | 용도 |
|------|------|
| `GET /health` | 헬스체크 (`model_ready`, `degraded` 노출) |
| `POST /synthesize` | 동기 합성 (짧은 텍스트) |
| `POST /synthesize/async` | 비동기 제출 → `job_id` (긴 메시지, 권장) |
| `GET /synthesize/status/{job_id}` | processing / done / error |
| `GET /synthesize/result/{job_id}` | 완료 wav 다운로드 |

---

## 2. 문제 로그 (증상 → 원인 → 해결)

### P-1. cloudflared URL이 재시작마다 바뀜
- **증상:** 등록한 URL이 며칠 뒤 죽고, 백엔드가 옛 URL 호출 → 실패
- **원인:** quick tunnel은 cloudflared 재시작 때마다 **새 랜덤 URL** 발급
- **해결(임시):** 재시작할 때마다 `/api/v1/tts/register-url` 재호출
- **해결(근본):** **Cloudflare Named Tunnel(고정 URL)** → 재등록 자체 제거

### P-2. degraded 상태 (GPU 정체) — async 503 / error
- **증상:** `/synthesize/async`가 503 또는 status="error", 메시지 "합성 시간 초과(GPU 정체)"
- **원인:** `server.py` 백그라운드 워커가 합성을 `_SYNTH_TIMEOUT=300초`로 제한.
  초과 시 `asyncio.TimeoutError` → `_degraded=True` 래치 → status="error".
  한 번 켜지면 **재시작 전까지** 모든 요청을 즉시 거절(죽음의 소용돌이 방지 장치).
- **해결:** `ai\tts\start_tts.bat` 재시작 → `_degraded=False` 리셋 + 큐 초기화
- **확인:** `/health`의 `degraded` 필드

### P-3. VRAM이 진짜 범인인가? (진단)
- **가설:** VRAM 고갈로 GPU stall → 300초 초과
- **진단 결과(깨끗한 GPU):** 합성 중 VRAM 최대 **6634/8151 MiB**, 합성 done(29.5초). **VRAM 여유 있음.**
- **결론:** 깨끗한 상태에선 VRAM 문제 아님. **다른 앱이 VRAM을 많이 먹을 때만** stall 발생
  (해결기록 #9: VSCode 18개 + Codex가 7692/8151 MiB 점유 → 합성 timeout).
- **해결:** 실험 전 무거운 GPU 앱 정리 / 브라우저 하드웨어 가속 끄기 (Zoom 제외)

### P-4. 양자화로 VRAM 줄이기 — 불가
- **증상:** bitsandbytes 양자화 시도 실패
- **원인:** RTX 5060 = Blackwell **sm_120**. bitsandbytes 커널이 sm_120 미지원(INT8 시 출력 깨짐).
  sm_120에서 되는 **AWQ**는 표준 transformer LLM 전용 → **커스텀 `qwen_tts` 라이브러리에 적용 불가**.
- **결론:** 양자화는 두 겹 장벽(신상 GPU + 커스텀 라이브러리)으로 **막다른 길**. VRAM은 운영으로 관리.

### P-5. Qwen3 스킵 → WaveSpeed/Google 폴백 (핵심)
- **증상:** 환주 서버 로그에 요청이 **안 옴** + 음성이 Google/gTTS로 나옴
- **원인(코드 확정):** 백엔드 `tts.py:154` `if tts_server_url:` 가 **False**.
  → Redis `tts:server_url`이 비어 있어 Qwen3(`_qwen3_remote`) 자체를 안 탐
  → `elif wavespeed_key:`(166)로 빠져 WaveSpeed 직행.
  Redis가 비는 이유 = **TTL 만료**(워치독이 안 돌아 자동 재등록 없음).
- **해결(임시):** 실험 직전 재등록 → 곧바로 실험(TTL 살아있는 동안)
- **해결(근본):** 백엔드 Redis `tts:server_url` **TTL 제거/연장**

### P-6. /api/v1/tts 가 폴백 없이 500
- **증상:** WaveSpeed 400 → 그대로 500 Internal Server Error
- **원인:** `tts.py:166`의 `elif` 가지는 `_wavespeed_tts`를 **raw 호출**(try/except 없음).
  반면 `if` 가지(164)는 `_wavespeed_or_google`로 감싸 폴백함 → **불일치**.
- **해결:** `tts.py:166` → `_wavespeed_tts` 대신 `_wavespeed_or_google` 사용 (gTTS까지 폴백, 500 방지)

### P-7. WaveSpeed 400 / Google GCP 인증 없음
- **증상:** 폴백 체인에서 WaveSpeed 400, Google ImportError
- **원인:** WaveSpeed payload 규격 불일치(voice/파라미터 추정) / GCP 인증 미설정
- **해결:** WaveSpeed 응답 body 로깅해 400 사유 확인 + payload 수정 / GCP 설정 또는 체인서 제거 (gTTS가 최종이라 동작은 함)

### P-8. GitHub push ≠ NCP 배포
- **증상:** 세종님이 fix push, 환주가 로컬 pull 했는데도 증상 그대로
- **원인:** 로컬 pull은 **환주 PC만** 변경. **NCP 백엔드(Docker)는 옛 코드 그대로** 실행 중.
- **해결:** NCP 서버에서 `git pull` + `docker compose up -d --build`(컨테이너 재빌드/재시작) → 윤한/세종 영역

### P-9. cloudflared 중복 + 죽은 URL 등록
- **증상:** `Get-Process cloudflared`에 2개, 백엔드가 죽은 URL(`developments-...`) 호출 → `NameResolutionError`
- **원인:** cloudflared 여러 번 실행 → 여러 URL 공존 → 등록값과 현재값 불일치
- **해결:** `Stop-Process -Name cloudflared`(cloudflared만, Zoom 무관) → 하나만 재시작 → 그 URL 재등록

### (참고) HTTP 206 Partial Content = 정상
- 앱이 MP3를 **range request**로 스트리밍하는 정상 동작. 에러 아님.

---

## 3. 명령어 레퍼런스 (PowerShell)

**헬스체크**
```powershell
Invoke-RestMethod -Uri http://localhost:8002/health
# model_ready: True, degraded: False 면 정상
```

**서버 재시작 (degraded 해제)**
```
ai\tts\start_tts.bat
```

**cloudflared 터널 시작**
```powershell
& "$env:LOCALAPPDATA\Microsoft\WinGet\Packages\Cloudflare.cloudflared_Microsoft.Winget.Source_8wekyb3d8bbwe\cloudflared.exe" tunnel --url http://localhost:8002/
```

**현재 URL 살아있나 확인** (`[URL]` 교체)
```powershell
(Invoke-WebRequest -Uri https://[URL].trycloudflare.com/health).StatusCode
# 200 = 정상 / 1033·502 = 죽음 또는 변경
```

**URL 백엔드 등록** (`[URL]` 교체)
```powershell
Invoke-RestMethod -Uri https://rainbow-bridge.duckdns.org/api/v1/tts/register-url -Method Post -Headers @{"X-TTS-Secret"="<팀_TTS_시크릿>"} -ContentType "application/json" -Body (@{url="https://[URL].trycloudflare.com"}|ConvertTo-Json)
# ok: True 면 등록 완료
```

**cloudflared 상태/중복 확인**
```powershell
Get-Process cloudflared -ErrorAction SilentlyContinue
```

**cloudflared 전부 종료 (중복 정리, cloudflared만 — Zoom 무관)**
```powershell
Stop-Process -Name cloudflared -Force
```

**VRAM 진단 (합성 중 추적, async 제출+폴링)**
```powershell
$b=@{text="테스트 문장";tone="girl"}|ConvertTo-Json
$job=Invoke-RestMethod -Uri http://localhost:8002/synthesize/async -Method Post -ContentType "application/json" -Body $b
$id=$job.job_id
do { Start-Sleep 5; nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader; $st=Invoke-RestMethod -Uri "http://localhost:8002/synthesize/status/$id" } while ($st.status -eq "processing")
$st
```

---

## 4. 백엔드 액션 아이템 (윤한·세종)

| 우선 | 항목 | 내용 |
|------|------|------|
| **P1** | Redis TTL | `tts:server_url` TTL 제거/연장(7일+). 만료 시 Qwen3 스킵의 근본 원인 |
| **P2** | 500 방지 | `tts.py:166` `_wavespeed_tts` → `_wavespeed_or_google`로 변경(폴백 일관성) |
| **P3** | WaveSpeed 400 | `_wavespeed_tts`에서 응답 body 로깅 → 400 사유 확인, payload(voice 등) 수정 |
| **P4** | Google 폴백 | GCP 인증 설정 또는 체인에서 제거(gTTS 최종이라 급하지 않음) |
| 배포 | NCP 반영 | GitHub fix는 NCP에서 `git pull` + `docker compose up -d --build` 해야 적용 |

---

## 5. 역할 분담

| 담당 | 책임 |
|------|------|
| **정환주** (GPU 서버) | 서버 healthy 유지 · degraded 시 재시작 · 현재 URL 재등록 · VRAM 여유 확보 |
| **윤한·세종** (백엔드) | Redis TTL · 폴백 일관성 · WaveSpeed payload · GCP · **NCP 실제 배포** |
| **민경** (프론트) | tone/perspective 파라미터 정확 전달 · `/emotions/recovery` 폴링 간격 조정 |

---

## 6. 핵심 교훈 & 근본 해결

1. **GitHub ≠ 운영 서버.** 코드 push 후 반드시 NCP에서 pull + 컨테이너 재시작해야 반영됨.
2. **로그에 요청이 안 오면** = 그 서버까지 도달 안 한 것 = 문제는 그 앞단(라우팅/등록/폴백).
3. **degraded는 자동 복구 안 됨.** 한 번 GPU 정체로 timeout 나면 재시작 전까지 유지.
4. **quick tunnel은 매번 URL이 바뀐다.** 이게 모든 URL 혼선의 근원.
5. **양자화는 sm_120 + 커스텀 라이브러리로 불가.** VRAM은 운영(앱 정리/가속 끄기)으로 관리.

**근본 해결 우선순위**
1. **Cloudflare Named Tunnel(고정 URL)** — URL 변경·재등록 자체를 없앰 (가장 큰 효과)
2. **Redis TTL 제거/연장** — 등록 만료로 Qwen3 스킵되는 문제 차단
3. **폴백 일관성(P2)** — 실패해도 500 대신 gTTS로 떨어지게
4. **VRAM 운영** — 실험 시 무거운 GPU 앱 정리

---

## 7. 부록: 코드 근거

**`backend/app/services/tts.py` — generate_tts 분기**
```python
tts_server_url = (Redis "tts:server_url"  or  env "TTS_SERVER_URL").strip()   # 149-150
wavespeed_key  = env "WAVESPEED_API_KEY"                                       # 152

if tts_server_url:                          # 154 — URL 있으면 Qwen3
    try:    result = await _qwen3_remote(...)            # 157
    except: result = await _wavespeed_or_google(...)     # 164 (폴백 O)
elif wavespeed_key:                         # 165 — URL 없으면
    result = await _wavespeed_tts(...)       # 166 ← 폴백 없이 500 (P2 대상)
else:
    result = await _google_tts_fallback(...) # 168
```

**`ai/tts/server.py` — degraded 발생점**
```python
_SYNTH_TIMEOUT = 300.0   # 합성 상한(초). 600자 ≈ 204초라 정상이면 통과
_degraded = False        # hang 1회 감지 시 True, 재시작 전까지 유지

# 백그라운드 워커
async with _gpu_sem:
    try:
        result = await asyncio.wait_for(run_in_threadpool(synthesize, text, tone),
                                        timeout=_SYNTH_TIMEOUT)          # 122-123
        _JOBS[job_id].update(status="done", ...)                        # 125
    except asyncio.TimeoutError:            # 131 — GPU 정체
        _degraded = True                    # 132
        _JOBS[job_id].update(status="error",
            error="합성 시간 초과(GPU 정체) — 폴백 전환")                # 134

# /health
"model_ready": _model_ready and not _degraded   # 188 — degraded면 false 노출
```
