# 🧠 AI 파트 할 일 (TODO)

> AI 파트 전반(`llm`·`tts`·`evaluation`·`liveportrait`) 세부 작업 목록입니다.
> 작업 규칙·윤리 경계는 [CLAUDE.md](CLAUDE.md), 전체 진행도는 [../docs/PROGRESS.md](../docs/PROGRESS.md) — 프로토타입 8개 기능 ✅ 8/8.
> 상태: ⬜ 시작 전 · 🟡 진행 중 · 🔵 리뷰(PR) · ✅ 완료 · ⛔ 막힘

---

## 📌 담당 (확정)

| 폴더 | 영역 | 담당 |
|------|------|------|
| `ai/llm/` | 추모 메시지(③)·미션 추천(⑤)·위기 감지(⑦)·provider·기념일/장례/감정추론 | 반소람 |
| `ai/tts/` | 음성 합성(④) — WaveSpeedAI 메인 + Qwen3/Google/gTTS 폴백 | 정환주 |
| `ai/evaluation/` | 평가 지표·집계(⑧) — 회복점수 4축, 폰사용/삼성헬스 분석 | 정환주·반소람 |
| GPU 인프라 | RTX 5060 서버·LivePortrait | 정환주·장민수 |

> 🎬 `ai/liveportrait/`는 멀티모달(장민수) 담당.

---

## 🟡 남은 일

- [ ] **L2~3 cap=41** — 회복점수 4축(`recovery_score_from_axes`)에 risk_level 기반 상한 적용 (백엔드 risk_level 연계 필요)
- [ ] p_미션/p_지속성/p_생활패턴/p_감정추세 실측값 확보 후 시뮬레이션 재검증
- [ ] L1/L0(0~45점)의 G×2+Sm×1 vs G×1+Sm×2 분기 기준(`emotion_score`) 유지/변경 여부 확정
- [ ] `RECOVERY_SCORE_DESIGN.md` 6장 cap 표기 정정(44→41, 79→없음)
- [ ] 평가 지표/스키마 최종 문서화 (`evaluation/`)

---

## ✅ 완료된 작업

### 결정 A·B·C (선행 결정)
- ✅ LLM: 로컬 엔진 대신 **Gemini API** 채택·실연동 (0-5, 06-03)
- ✅ AI ↔ 백엔드 통합 방식 확정 — `ai/llm`·`ai/evaluation` 모듈을 백엔드 `services/`에서 직접 호출
- ✅ 입출력 스키마 확정 — 아래 각 기능 API와 합의 완료

### L-0. 공통 기반 (provider)
- ✅ `provider.py` — Gemini 호출 추상화, 타임아웃·재시도·예외 처리(graceful)
- ✅ `config.py` — 모델·온도 파라미터

### L-③. 추모 메시지 생성
- ✅ `memorial.py` + `prompts/memorial.py` — Gemini 실연동, RAG(`comfort` 카테고리) 적용
- ✅ 1인칭/3인칭 프롬프트 최종본 동결(06-15), 가드레일 테스트 통과
- ✅ 위기 감지(`safety.detect_crisis`) 선호출 연계
- ✅ API 연동(모세종) — `POST /messages`

### L-⑤. 미션 추천
- ✅ `mission.py` + `prompts/mission.py` — LLM + 규칙 폴백, 미션 풀 60개
- ✅ 레벨별(L2~3/L1/L0) 난이도 조합(`mission_composition`), `difficulty` 3단계 태깅(레거시 경로 포함)
- ✅ L0 active 전환 임계값 45 확정
- ✅ API 연동(모세종) — `GET /missions/{pet_id}`, `PATCH /complete`

### L-⑦. 위기 감정 감지 🚨
- ✅ 위험 등급 4단계(L0~L3) + `subject`(self/pet/other) 구분
- ✅ L0 규칙 레이어 + L1 LLM 분류(`prompts/safety.py`, json_mode) + 보수적 융합
- ✅ `safety.detect_crisis()` — 골든셋 30개 통과, 미탐 0
- ✅ `CRISIS_HOTLINE`(1393) 상수화, 위기 로그 PII 최소화
- ✅ API 연동(모세종) — risk_level 2+ 시 1393 안내 자동 삽입

### 부가 모듈 (반소람)
- ✅ `anniversary.py`/`funeral.py`/`terminal_care.py`/`emotion_inference.py`/`usage_observation.py` + 각 prompts — 기념일·장례 안내(RAG `funeral`)·시한부 케어·감정추론·폰사용 관찰

### 🎙️ ai/tts — MVP ④ (정환주)
- ✅ 엔진: **WaveSpeedAI 메인** + Qwen3 GPU + Google Cloud + gTTS 4단계 폴백 (PR #275)
- ✅ 톤 옵션(`TtsTone`: warm/calm/hopeful/soft) + 속도·피치 매핑
- ✅ `tts.synthesize()` + 긴 텍스트 분할, URL 자동 핸드오프 (PR #285)
- ✅ API 연동 — `POST /tts`, 메시지 생성 시 narration TTS 사전 생성 (PR #277)

### 📊 ai/evaluation — MVP ⑧ (정환주·반소람)
- ✅ 평가 지표 정의 + `llm_logs` 스키마/`save_log`(원문 PII 미저장)
- ✅ `build_report(...)` 순수 함수 + `GET /report/{pet_id}` 노출
- ✅ 회복점수 4축 일원화 `recovery_score_from_axes`(미션40/지속성30/감정추세15/생활패턴15, 무페널티 재정규화) — 게이트·리포트 동일 산식 (PR #284·#286, 06-15)
- ✅ 생활패턴(걸음/수면/야간폰사용) DB 배선 — `health_signal.py` + `backend/app/services/health_lifestyle.py` (06-15)
- ✅ 감정추론(`emotion_inference`)·폰사용 분석(`phone_usage`)·삼성헬스 파서(`load_samsung_export`, `health_export_adapter`)
- ✅ 옛↔새 산식 비교 스크립트 `compare_gate_scores.py`
- ✅ 샘플 데이터 집계 검증 — `test_report`·`test_recovery_signal`·`test_health_signal`·`test_report_service`

---

## ✅ 완료 기준 (Definition of Done)

- [x] Gemini 연동 (provider 추상화)
- [x] 출력에 반려동물 1인칭/부활 표현 없음 (가드레일 테스트 통과)
- [x] 위기 입력 시 1393 안내가 항상 우선, 미탐 0 (골든셋 통과)
- [x] 입출력 스키마가 백엔드와 일치
- [x] `ruff`·`black` 통과, 핵심 함수 테스트 존재
- [ ] 평가 지표/스키마 최종 문서화 (위 "남은 일" 참고)
