# Qwen3-TTS 클라우드 API 전환 조사 (2026-06-12, 정환주)

> "지금 로컬 GPU 로 돌리는 Qwen3-TTS 를 **API 로 박아놓을 수 있나**" 조사.
> 결론: **API 있음. 단 우리 목소리는 그대로 못 옮기고 '클로닝'으로 다시 떠야 함.**
> 비용은 **신규계정 무료할당으로 프로토타입은 거의 공짜**, 상용은 소액 종량.
> (기술 몰라도 §1·§4·§6 만 보면 됩니다.)

---

## 1. 한 줄 결론

- **클라우드 API 존재** — DashScope(Alibaba Cloud Model Studio)가 우리가 쓰는 Qwen3-TTS 를 API 로 제공.
- 전환하면 **GPU 상시가동·cloudflared 터널·콜드스타트·동시성 제약·정환주 PC 의존 전부 사라짐.**
- ⚠️ **"음성 다시 안 만들어도 됨"은 절반만 맞음** — 우리 로컬은 seed 고정 VoiceDesign 이라 같은 목소리를 API 에 그대로 못 박음. **기존 샘플 wav 를 클로닝**해야 제일 근접.
- 비용: 신규계정 **90일 무료할당**으로 프로토타입/시연은 사실상 무료. 상용은 문자수 종량(소액). **단 공식 합성 단가는 이번 조사에서 1차출처로 확정 못 함 → 계정 만들고 콘솔 단가표로 확정 필요(§4).**

---

## 2. 지금 우리 방식 (왜 그대로 못 옮기나)

[`ai/tts/qwen3_synthesize.py`](qwen3_synthesize.py) 기준 — 우리는 **프리셋 보이스가 아니라 VoiceDesign + seed 고정**입니다.

| 보이스 | 만든 방식 | seed |
|---|---|---|
| boy | 다이얼(gender/age/warmth/pitch/emotion…)로 디자인 | 29018 |
| girl | 〃 | 46286 |
| woman | 〃 (성인 여성 나레이션, 세종님 확정) | 21424 |

- **seed = 화자 ID.** 이 난수는 **우리 로컬 모델 내부** 값이라, API 에 같은 seed 를 넣어도 **같은 목소리가 안 나옵니다.** (모델 가중치·런타임이 다름)
- 그래서 API 로 가면 목소리는 **새로 떠야** 합니다 → §3 참고.

---

## 3. API 방식 3종 + 우리 목소리 유지 경로

DashScope 합성 엔드포인트 (싱가포르 리전):
```
POST https://dashscope-intl.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation
Authorization: Bearer $DASHSCOPE_API_KEY
{ "model": "qwen3-tts-flash",
  "input": { "text": "...", "voice": "<보이스>", "language_type": "Korean" } }
```
- 한국어 지원 ⭕ / 반환: 비스트리밍=오디오 **URL(24h 유효)**, 스트리밍=base64
- 과금은 **문자수 기준**(응답에 `usage.characters` 찍힘)

**우리 목소리를 어떻게 마련하나 — 3택:**

| 경로 | 내용 | 우리 목소리 유지 | 생성 비용 |
|---|---|---|---|
| **(A) Voice Cloning** ✅추천 | 이미 만든 샘플 wav(`ai/tts/_output`) **10~20초**(최대 60s, 16-bit WAV/MP3/M4A) 업로드 → 클론 → `voice_id` 발급. **영구 보존.** | 제일 근접(우리 샘플 복제) | **$0.01/개**, 90일 **1000개 무료** |
| (B) Voice Design | 다이얼값을 **글 묘사**(성별·나이·톤·감정)로 다시 디자인 | 비슷하지만 미묘하게 다름 | **$0.20/개**, 90일 **10개 무료** |
| (C) 프리셋 9종 | Alibaba 기본 보이스(Vivian/Serena/Ryan… 한국어 지원) 그대로 | 우리 목소리 버림 | 추가 생성비 없음 |

> 사용자가 원하는 "음성 다시 안 만들고 박기"에 제일 가까운 건 **(A) 클로닝**. 우리 샘플 wav 가 이미 있으니 업로드만 하면 됨. 클론 생성은 90일 1000개 무료라 우리 3개 = **사실상 공짜.**

---

## 4. 💰 비용 (사용자 주 관심사 — 정직하게)

### 4-1. 검증된 사실 (1차출처 확인됨)
| 항목 | 비용 | 출처 신뢰도 |
|---|---|---|
| **신규계정 무료할당** | 모델당 100만 토큰 ×수십개 모델(70M+), **90일**, **싱가포르 리전** 한정 | 공식(§7) |
| Voice Cloning 생성 | **$0.01/개**, 90일 1000개 무료 | 공식 |
| Voice Design 생성 | **$0.20/개**, 90일 10개 무료 | 공식 |
| 합성 과금 단위 | **문자수 기준**(`usage.characters`) | 공식 API 문서 |

### 4-2. 합성 단가 — ⚠️ 미확정
- 공식 DashScope 페이지가 이번 조사에서 **계속 404** 났고, 가격집계 사이트(CloudPrice 등 2026-06-11 기준)도 TTS 행이 **공란**이라 **1차출처로 못 박았습니다.**
- 참고용 추정치(서드파티 게이트웨이, 공식 아님):
  - WaveSpeedAI: **$0.02/run** (~50건/$1)
  - 한 블로그: **만 자당 ~$1** (≈ $0.0001/자)
- → **결론: 계정 만들고 콘솔 "Pricing Calculator/단가표"에서 직접 확인해야 확정.** 아래 추정은 이 미확정 단가 기반이라 ±폭 있음.

### 4-3. 우리 시나리오 추정 (단가 미확정 → 어림)
추모 메시지 한 건 **~150자** 가정:
- **보이스 셋업**: 클로닝 3개 = $0.03 → 90일 무료라 **$0**
- **합성 1건**: 위 추정 두 기준 모두 **약 20~30원/건** 수준
- **프로토타입/시연 단계**: 신규계정 90일 무료할당으로 **사실상 무료**일 가능성 높음(단 TTS가 토큰무료할당에 포함되는지 콘솔 확인 필요)
- **상용 가정**: 하루 1000건 × 30원 ≈ **월 수만 원** 수준(트래픽 비례)

### 4-4. 비용 안 드는 대안도 명시
- **지금처럼 로컬 GPU 유지 = 추론 비용 $0** (전기료 외). 운영 번거로움(터널·콜드스타트)은 이미 §대기큐·cloudflared 로 상당부분 잡아둠.
- 즉 "돈 한 푼도 안 쓴다"가 최우선이면 **로컬 유지가 정답.** API 는 *운영 편의를 돈으로 사는* 선택.

---

## 5. 백엔드 영향 (윤한 영역)

- 지금: [`backend/app/services/tts.py`](../../backend/app/services/tts.py) `_qwen3_remote` 가 우리 `server.py /synthesize` 에 POST → wav 바이트 수신.
- API 전환 시: 엔드포인트를 **DashScope** 로 교체 + `Bearer` 키 헤더 + body 형식(`input.text/voice/language_type`) + **오디오 URL 다운로드**로 변경.
- 대신 **폐기 가능**: `ai/tts/server.py`, GPU 상시가동, cloudflared 터널, `gpu_server_start.ps1` 자동기동, `.env` URL 매번 갱신 전부 불필요.
- 폴백(Google/gTTS) 로직은 그대로 두면 API 장애 시 안전망 유지.

---

## 6. 결정 필요 (팀/PM)

1. **Alibaba Cloud 계정 + 해외결제수단(카드) + API 키 발급** 필요 — 가입·실명/결제 절차 있음.
2. 목소리 경로 **(A) 클로닝 / (B) 재설계 / (C) 프리셋 중 택1** — 추천 **(A)**.
3. **데이터 처리 위치** (※"유출" 아님 — 정상적인 클라우드 API 동작):
   - 클라우드 API 는 원래 텍스트를 벤더 서버로 보내 처리하는 구조. 해킹/유출이 아님.
   - **우리는 이미 그렇게 운영 중** — LLM=Gemini(구글), TTS 폴백=Google Cloud TTS → 지금도 텍스트가 구글 서버로 감. Alibaba 도 **같은 범주**.
   - 그래도 짚는 이유: (a) Alibaba=**중국 기업**이라 조직/정책 민감도가 구글보다 클 수 있음, (b) 추모 글이 **감정적으로 민감**한 데이터.
   - 로컬 유지 시에만 데이터가 외부로 아예 안 나감.
4. **무료할당 소진 후 단가** 콘솔에서 확정 후 월비용 시뮬.

### 로컬 vs API 한눈에
| | 로컬(현행) | 클라우드 API |
|---|---|---|
| 추론 비용 | **$0**(전기료만) | 종량(소액, 단가 확정필요) |
| 데이터 | **안 나감** | 해외 전송 |
| 우리 목소리 | **seed 정확 재현** | 클론/재설계 필요(근사) |
| 운영 | GPU·터널·콜드스타트·내PC 의존 | **전부 없음, 어디서나 안정** |
| 동시성 | 1건씩(대기큐) | 클라우드가 알아서 |

---

## 7. 출처

- [Qwen3-TTS GitHub](https://github.com/QwenLM/Qwen3-TTS)
- [Voice cloning — Alibaba Model Studio](https://www.alibabacloud.com/help/en/model-studio/qwen-tts-voice-cloning)
- [Voice design API — Alibaba Model Studio](https://www.alibabacloud.com/help/en/model-studio/qwen-tts-voice-design)
- [Qwen-TTS synthesis API](https://www.alibabacloud.com/help/en/model-studio/qwen-tts-api)
- [신규 무료할당 — Alibaba Model Studio](https://www.alibabacloud.com/help/en/model-studio/new-free-quota)
- [qwen3-tts-flash — AI/ML API](https://docs.aimlapi.com/api-references/speech-models/text-to-speech/alibaba-cloud/qwen3-tts-flash)
- [Qwen3 TTS Flash — WaveSpeedAI(서드파티 단가)](https://wavespeed.ai/models/alibaba/qwen3-tts-flash)
- [Qwen3 TTS VoiceDesign — CloudPrice(2026-06-11 기준, TTS행 공란)](https://cloudprice.net/models/alibaba-qwen3-tts-voicedesign)

> ⚠️ 합성 **공식 단가는 미확정**(공식 페이지 404·집계 공란). 계정 발급 후 콘솔 단가표로 반드시 확정할 것.
> GPU 서버 코드 변경분은 아직 **깃 미푸시**(정환주 PC). 전환 결정 시 PR.
