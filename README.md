# 🌈 레인보우 브릿지 (Rainbow Bridge)

> 반려동물의 시한부 선고부터 회복까지, **이별 전 과정을 함께하는 AI 케어 서비스**

[![Status](https://img.shields.io/badge/status-prototype-brightgreen)]()
[![Period](https://img.shields.io/badge/period-2026.06.01~06.19-blue)]()
[![PRs](https://img.shields.io/badge/PRs-262-orange)]()

---

## 📌 이게 뭔가요?

수의사로부터 **시한부 선고**를 받은 순간부터 — 남은 시간 동안의 추억 기록, 장례, 그리고 펫로스 회복까지 보호자 곁에 있는 서비스입니다.

**연계형(B2B2C)** — 장례업체·병원이 채널·지불자, 보호자는 무료.

| 구분 | 우리가 하는 것 | 우리가 안 하는 것 |
|------|----------------|-------------------|
| 생전 | 버킷리스트·사진 기록, 추억 쌓기 | 일반 반려동물 케어 앱 대체 |
| 장례 | 장례 절차 안내·연계 | 직접 장례 서비스 제공 |
| 사후 | AI 추모 메시지·영상·일상 복귀 미션 | 반려동물 부활 / AI 실제 대화 |
| 위기 | 감정 감지 → 1393 즉시 안내 | 전문 심리치료 대체 |

> "아이가 강아지별로 이사를 준비하고 있어요. 남은 시간동안 가서도 행복하게 좋은 추억 만들어 보아요."

---

## ✨ 핵심 기능 (프로토타입)

| # | 기능 | 설명 | 상태 |
|---|------|------|------|
| ① | 반려동물 프로필 입력 | 이름·종·함께한 기간·추억 등 | ✅ |
| ② | 보호자 감정 체크인 | 오늘의 감정 상태 기록 + 위기 감지 (L0~L3) | ✅ |
| ③ | AI 추모 메시지 생성 | Gemini AI 개인화 위로 메시지 (RAG 기반) | ✅ |
| ④ | TTS 음성 낭독 | Qwen3 GPU 서버 비동기 폴링, warm·calm·hopeful 톤 | ✅ |
| ⑤ | 일상 복귀 미션 추천 | 회복 단계별 행동 미션 (AI+RAG) | ✅ |
| ⑥ | 추모 타임라인 | 감정·메시지·미션 기록 시간순 보관 | ✅ |
| ⑦ | 위기 감정 안전 라우팅 | risk_level L0~L3, L2↑ → 1393 즉시 안내 | ✅ |
| ⑧ | 회복 평가 리포트 | 감정 추이·미션 완료율·회복 지수 시각화 | ✅ |

**단계별 케어 모듈(AI):** 증상진료 안내 ✅ · 장례절차 상담 ✅ · 기념일 케어(D+30·D+100) ✅

**멀티모달(가산):** 사진 → LivePortrait → 동물 영상 → TTS 합성 → MP4+GIF 다운로드 ✅

> 진행 상황: [docs/PROGRESS.md](docs/PROGRESS.md) · 회복 지수 설계: [docs/RECOVERY_SCORE_DESIGN.md](docs/RECOVERY_SCORE_DESIGN.md)

---

## 🧱 기술 스택

| 영역 | 기술 |
|------|------|
| Backend | FastAPI (Python), MongoDB, Redis |
| Frontend | React Native + Expo SDK 54 (Android/iOS) |
| AI / LLM | Gemini API (`gemini-2.5-flash`) |
| RAG | ChromaDB (comfort · mission · funeral · vet_protocol) |
| TTS | Qwen3 (GPU 서버, 비동기 폴링) + Google Cloud TTS 폴백 |
| 멀티모달 | LivePortrait (GPU 서버, Cloudflare Tunnel), FFmpeg |
| Infra | NCP Cloud Server, Docker Compose (healthcheck), GitHub Actions CI/CD |

자세한 구조: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

---

## 📁 폴더 구조

```
rainbow-bridge/
├── backend/          # FastAPI 백엔드 (모세종, 김윤한)
│   ├── app/
│   │   ├── api/      # 라우터 (엔드포인트)
│   │   ├── services/ # 비즈니스 로직
│   │   ├── schemas/  # 요청/응답 스키마 (Pydantic)
│   │   ├── models/   # DB 모델
│   │   └── db/       # DB 연결
│   └── tests/
├── frontend-rn/      # React Native + Expo 앱 (민경이) ← 현행
│   ├── app/          # 화면 (Expo Router)
│   ├── api/          # 백엔드 API 호출
│   └── components/   # 공통 컴포넌트
├── frontend/         # ⚠️ 구버전 (Vite+React) — 더 이상 사용 안 함
├── ai/               # AI 엔진 (반소람, 정환주)
│   ├── llm/          # 추모 메시지·위기 감지·케어 모듈
│   ├── tts/          # 음성 합성
│   ├── liveportrait/ # 사진→영상 (장민수)
│   └── evaluation/   # 평가 리포트·회복 지수
└── docs/             # 📚 문서
    ├── ARCHITECTURE.md          # 시스템 구조
    ├── PROGRESS.md              # 프로토타입 진행도
    ├── RECOVERY_SCORE_DESIGN.md # 회복 지수 설계
    ├── SERVICE_FRAME.md         # 서비스 범위·기능 틀
    ├── ETHICS_추모표현_가이드.md  # 추모 표현 허용/금지 경계
    ├── CONTRIBUTING.md          # 협업 규칙
    ├── GIT_GUIDE.md             # Git 사용법
    ├── SETUP.md                 # 개발 환경 셋업
    ├── IOS_BUILD_GUIDE.md       # EAS iOS 빌드 가이드
    ├── scrum/                   # 스크럼 기록
    ├── devlog/                  # 개발일지 (통합 + 팀원별)
    └── archive/                 # 구버전 문서 보관
```

---

## 🚀 빠른 시작

> 처음 합류했다면 아래 순서대로 읽으세요.

1. 📖 [docs/GIT_GUIDE.md](docs/GIT_GUIDE.md) — Git·브랜치·커밋 (가장 먼저!)
2. 🤝 [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md) — 협업 규칙
3. ⚙️ [docs/SETUP.md](docs/SETUP.md) — 개발 환경 세팅
4. 🗺️ [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — 전체 구조
5. ✅ [docs/PROGRESS.md](docs/PROGRESS.md) — 내가 맡은 일

```bash
# 백엔드
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload        # http://localhost:8000/docs

# 프론트엔드 (React Native + Expo)
cd frontend-rn
npm install
npx expo start                       # Expo Go 앱으로 QR 스캔

# 환경 변수
cp .env.example .env                 # 백엔드
# frontend-rn/ : EXPO_PUBLIC_API_URL=http://YOUR_IP:8000
```

> 실서버: https://rainbow-bridge.duckdns.org (프론트) · https://rainbow-bridge.duckdns.org/api (API)

---

## 👥 팀 (팀 5)

| 이름 | 역할 | 주 폴더 |
|------|------|---------|
| 모세종 | PM + 백엔드 | `backend/` |
| 김윤한 | 백엔드 / 홈서버 | `backend/`, 인프라 |
| 반소람 | AI 엔지니어 | `ai/llm/` |
| 정환주 | AI 엔지니어 / GPU 서버 | `ai/`, GPU 인프라 |
| 민경이 | 프론트엔드 | `frontend-rn/` |
| 장민수 | 멀티모달 | `ai/liveportrait/` |

---

## 📅 일정

- **2026-06-01** 프로젝트 시작 / 레포 셋업
- **2026-06-19** 발표

---

## 📜 안내

교육 과정 팀 프로젝트입니다. 위기 상황 안내 번호(**1393**)는 임의로 변경하지 마세요.
