# TTS 서버 실행 가이드 (정환주용)

> 내가 직접 켜고 끄는 법. 위에서부터 **A → B → C 순서**로 하면 됨.
> 서버는 pm2로 켜고, 외부 접속은 cloudflared 터널로 연다.

---

## ✅ 켜는 순서 (A → B → C)

### A. 서버 켜기 (pm2)

PowerShell 창에 붙여넣기:

```powershell
pm2 start C:\Rainbow_Bridge\Rainbow-Bridge\ai\tts\ecosystem.config.js
```

- 실행하면 **서버 창(검은 콘솔) 하나가 뜬다 = 정상**. 그게 서버 본체다. 닫지 말고 그냥 둔다.
- 잘 떴는지 확인:

```powershell
pm2 list                                          # status 가 online 이면 OK
Invoke-RestMethod http://localhost:8002/health    # model_ready:True, degraded:False 면 준비 끝
```

> ⚠️ `pm2` 가 "인식 안 됨" 뜨면 → PowerShell 창을 **새로 하나 열어서** 다시. 그래도 안 되면 `pm2` 대신:
> `& "C:\Users\ghksw\AppData\Roaming\npm\pm2.ps1" list` 처럼 전체 경로로 쓴다.

---

### B. 터널 켜기 (cloudflared)

**새 PowerShell 창**을 하나 더 열고 붙여넣기. **이 창은 닫으면 안 됨**(닫으면 터널 죽음):

```powershell
& "$env:LOCALAPPDATA\Microsoft\WinGet\Packages\Cloudflare.cloudflared_Microsoft.Winget.Source_8wekyb3d8bbwe\cloudflared.exe" tunnel --url http://localhost:8002/
```

- 출력 중간에 이런 줄이 나온다:
  `https://무슨무슨-어쩌고.trycloudflare.com`  ← **이 주소를 복사**한다.
- 이 주소는 **켤 때마다 매번 바뀐다**(quick tunnel). 그래서 켤 때마다 아래 C(등록)를 다시 해야 함.

---

### C. 주소 등록 (백엔드에 알려주기)

**또 다른 새 창**에서, B에서 복사한 주소를 `[복사한주소]` 자리에 넣고 실행:

```powershell
Invoke-RestMethod -Uri https://rainbow-bridge.duckdns.org/api/v1/tts/register-url -Method Post -Headers @{"X-TTS-Secret"="rainbow-tts-secret-2026"} -ContentType "application/json" -Body (@{url="https://[복사한주소].trycloudflare.com"}|ConvertTo-Json)
```

- `ok: True` 가 나오면 **완료**. 이제 백엔드가 이 주소로 TTS를 호출한다.

---

## ⏹️ 끄는 법

| 끄는 것 | 명령 / 방법 |
|---|---|
| 서버 | `pm2 delete qwen3`  (잠깐 멈추기만: `pm2 stop qwen3`) |
| 터널 | cloudflared 창을 닫는다  (또는 `Stop-Process -Name cloudflared -Force`) |

---

## 🔁 자주 쓰는 명령 (외워두면 편함)

| 상황 | 명령 |
|---|---|
| 서버 상태 보기 | `pm2 list` |
| 서버 건강 확인 | `Invoke-RestMethod http://localhost:8002/health` |
| 서버 로그 보기 | `pm2 logs qwen3` |
| 서버 재시작 (degraded 풀 때) | `pm2 restart qwen3` |
| 터널 살아있나 확인 | `(Invoke-WebRequest https://[주소].trycloudflare.com/health).StatusCode` (200=정상) |
| 터널 중복 정리 | `Stop-Process -Name cloudflared -Force` (cloudflared만, Zoom 무관) |

---

## ❓ 헷갈릴 때

- **검은 콘솔 창이 떠 있다** → 서버 본체다(A에서 뜬 것). 정상. 닫지 마라.
- **`health` 에 `degraded:True`** → 서버는 떠 있는데 합성이 한 번 멈췄던 상태. `pm2 restart qwen3` 하면 풀린다.
- **백엔드가 TTS 못 부른다** → 터널 주소가 바뀐 것. B로 새 주소 확인 → C로 다시 등록.
- **컴퓨터를 껐다 켰다** → A부터 다시(서버 + 터널 둘 다 다시 켜야 함). 자동으로 안 올라온다.

---

## 📌 메모

- 서버 포트: `8002`
- 백엔드 도메인: `https://rainbow-bridge.duckdns.org`
- 등록 비밀키 헤더: `X-TTS-Secret: rainbow-tts-secret-2026`
- pm2 설정 파일: `ai/tts/ecosystem.config.js` (이건 한 번 만들어둔 거라 건드릴 일 없음)
- `start_tts.bat` 은 **이제 쓰지 않는다** (pm2 와 충돌). pm2 로 켠다.
