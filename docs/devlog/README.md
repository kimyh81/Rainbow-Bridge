# 📓 통합 개발일지

레인보우 브릿지 팀 전체 개발 기록입니다.
**날짜별 한 줄 요약 + 개인 일지 링크** 구조예요.

- 개인 상세 일지는 [`members/`](members/) 안에 사람별로 있습니다.
- 매일 작업 끝나면 → **본인 개인 일지에 작성** → 여기 통합 일지에 한 줄 요약 추가.

## ✍️ 작성 규칙
1. 본인 일지([`members/이름.md`](members/))에 날짜 섹션을 **맨 위**에 추가 (최신 날짜가 위로).
2. 아래 통합 일지 표에 그날 한 일을 **한 줄**로 요약 + 본인 일지로 링크.
3. 형식은 개인 일지 파일 상단 템플릿 참고.

### 멤버 일지
- [모세종 (PM/백엔드)](members/모세종.md)
- [김윤한 (백엔드)](members/김윤한.md)
- [반소람 (AI 엔지니어)](members/반소람.md)
- [정환주 (AI 엔지니어)](members/정환주.md)
- [민경이 (프론트엔드)](members/민경이.md)
- [장민수 (멀티모달)](members/장민수.md)

---

## 📊 파트별 MVP 진행도 (PM 대시보드)

> **부족한 곳을 한눈에** 보기 위한 파트 기준 롤업입니다.
> 상세 체크·각자 갱신은 [PROGRESS.md](../PROGRESS.md)가 원본 — 여기는 파트별로 묶어서 봅니다.
> 상태: ⬜ 시작 전 · 🟡 진행 중 · 🔵 리뷰 중 · ✅ 완료 · ⛔ 막힘
> **최종 갱신:** 2026-06-13

### 파트별 요약

| 파트 | 담당 | 완료/전체 | 비고 |
|------|------|-----------|------|
| 공통 셋업 | 전원 | 8/8 | 전체 완료 |
| 백엔드 API | 모세종·김윤한 | 8/8 | 전체 완료 |
| AI/LLM | 반소람·정환주 | 5/5 + 회복지수 재설계 중 | 회복 점수 산식 확정 대기 |
| 프론트 화면 | 민경이 | 8/8 | 전체 완료 (SDK 54 업그레이드) |
| 멀티모달 | 장민수 | 4/4 | 전체 완료 |

### 🟦 공통 셋업
| 항목 | 담당 | 상태 |
|------|------|------|
| Git 레포 & 문서 | 모세종 | ✅ |
| FastAPI 뼈대 | 모세종 | ✅ |
| MongoDB 연결 + 실서버 | 김윤한·모세종 | ✅ |
| Docker / compose | 김윤한·모세종 | ✅ healthcheck + restart: always (PR #251) |
| LLM 결정·세팅 (Gemini) | 반소람·정환주 | ✅ |
| PERSO API 연동 테스트 | 장민수 | ✅ 드랍 확인 → LivePortrait 대체 |
| GPU 서버 셋업 (RTX 5060) | 정환주 | ✅ |
| 프론트 프레임워크 결정 | 민경이 | ✅ |

### 🟩 백엔드 API (모세종 · 김윤한)
| MVP 기능 | 담당 | 상태 |
|------|------|------|
| ① 반려동물 프로필 | 모세종 | ✅ |
| ② 감정 체크인 | 모세종·김윤한 | ✅ |
| ③ 추모 메시지 API 연동 | 모세종 | ✅ |
| ④ TTS API 연동 | 모세종·정환주 | ✅ 비동기 폴링 방식 (PR #260) |
| ⑤ 일상 복귀 미션 | 모세종 | ✅ |
| ⑥ 추모 타임라인 (DB) | 김윤한 | ✅ |
| ⑦ 안전 라우팅(1393) | 모세종 | ✅ |
| ⑧ 평가 리포트 | 모세종 | ✅ |

### 🟨 AI / LLM (반소람 · 정환주)
| 항목 | 담당 | 상태 |
|------|------|------|
| ③ 추모 메시지 프롬프트/LLM | 반소람 | ✅ |
| ⑤ 미션 추천 로직 | 반소람 | ✅ |
| ⑦ 위기 감정 감지 로직 | 반소람 | ✅ |
| ④ TTS 엔진 (Qwen3) | 정환주 | ✅ |
| ⑧ 평가 지표/집계 | 정환주 | ✅ |
| 회복 지수 재설계 | 반소람 | 🟡 산식 확정 중 ([설계문서](RECOVERY_SCORE_DESIGN.md)) |

### 🟪 프론트 화면 (민경이)
| 화면 | 상태 | | 화면 | 상태 |
|------|------|--|------|------|
| ① 프로필 입력 | ✅ | | ⑤ 미션 추천 | ✅ |
| ② 감정 체크인 | ✅ | | ⑥ 타임라인 | ✅ |
| ③ 추모 메시지 | ✅ | | ⑦ 안전 안내 UI | ✅ |
| ④ TTS 재생 | ✅ | | ⑧ 평가 리포트 | ✅ |

### 🟧 멀티모달 — 사진→영상 (장민수)
| 항목 | 담당 | 상태 |
|------|------|------|
| 사진 업로드 API | 모세종 | ✅ |
| LivePortrait 파이프라인 | 장민수 | ✅ |
| 영상+TTS 합치기 (FFmpeg) | 장민수 | ✅ |
| remote 추론(GPU 서버) | 장민수 | ✅ MP4 완료 후 GIF 백그라운드 생성 (PR #250) |
| PERSO 립싱크(선택형) | 장민수 | ✅ 드랍 확인 |
| 다운로드 제공 | 김윤한 | ✅ |

> 🔎 **PM 체크 포인트:** 표에서 ⬜/⛔ 가 몰린 파트 = 지금 도와줘야 할 곳.
> 매일 개인 일지 작성 시 본인이 바꾼 상태를 위 표(또는 PROGRESS.md)에 반영해 주세요.

---

## 2026-06-13 (Day 13)

| 이름 | 한 일 (요약) | 상세 |
|------|------------|------|
| 모세종 | PR #257~#261 CI수정·머지, 회복지수 설계문서 작성, 서비스계정키 gitignore 추가 | [→](members/모세종.md) |
| 김윤한 | — | [→](members/김윤한.md) |
| 반소람 | — | [→](members/반소람.md) |
| 정환주 | — | [→](members/정환주.md) |
| 민경이 | — | [→](members/민경이.md) |
| 장민수 | — | [→](members/장민수.md) |

**팀 전체:** PR #257~#261 전량 머지 완료. 전체 PR 260개 달성. 회복 지수 재설계 문서화(소람님 산식 확정 대기).

---

## 2026-06-12 (Day 12)

| 이름 | 한 일 (요약) | 상세 |
|------|------------|------|
| 모세종 | TTS 무음 버그·LP GIF 비동기 job·Docker healthcheck·서버 안정화 | [→](members/모세종.md) |
| 김윤한 | — | [→](members/김윤한.md) |
| 반소람 | LP GIF 세마포어 타임아웃 조정·Cloudflare Tunnel 교체 | [→](members/반소람.md) |
| 정환주 | TTS Cloudflare Tunnel 교체·Qwen3 API 검토 | [→](members/정환주.md) |
| 민경이 | Expo SDK 54 업그레이드·추모영상 자동생성 연결·온보딩 디자인 머지 | [→](members/민경이.md) |
| 장민수 | 온보딩 라우팅·UI 개선·윤리 동의 체크박스 추가, 사진 자동선택 파이프라인 분석 | [→](members/장민수.md#2026-06-12-day-12) |

**팀 전체:** 주요 버그 전량 수정 완료(PR #244~#254). ngrok → Cloudflare Tunnel 전환. 사진 자동선택 → 추모영상 파이프라인 프론트 연결 완료.

---

## 2026-06-01 (Day 1)

| 이름 | 한 일 (요약) | 상세 |
|------|------------|------|
| 모세종 | 레포 뼈대 + 협업 문서 6종 + FastAPI 진입점 셋업, GitHub 푸시 | [→](members/모세종.md#2026-06-01-day-1) |
| 김윤한 | — | [→](members/김윤한.md) |
| 반소람 | — | [→](members/반소람.md) |
| 정환주 | — | [→](members/정환주.md) |
| 민경이 | — | [→](members/민경이.md) |
| 장민수 | — | [→](members/장민수.md) |

**팀 전체:** 프로젝트 협업 기반 구축 완료. 레포 공개, 필독 문서 정비.

---

## 2026-06-02 (Day 2)

| 이름 | 한 일 (요약) | 상세 |
|------|------------|------|
| 모세종 | 반려동물·감정·미션 API 완성, 위기감지+1393, CI 강화(paths-filter·required), 서비스 시나리오 HTML, PR 10건+ 머지 | [→](members/모세종.md#2026-06-02-day-2) |
| 김윤한 | 홈서버 FastAPI+MongoDB 연동, 타임라인·어드민 API 완성, PR #12 제출 | [→](members/김윤한.md) |
| 반소람 | 위기 감지 규칙 레이어+골든셋 20종(PR #11), 추모 메시지 프롬프트·생성 로직·가드레일 테스트 10종(PR #21) | [→](members/반소람.md#2026-06-02-day-2) |
| 정환주 | LLM 비교 후 EXAONE→Gemini 전환 결정, smoke_gemini.py, 서비스 시나리오 3단계 문서(PR #17), TTS·평가 골격 스텁(PR #19) | [→](members/정환주.md#2026-06-02-day-2) |
| 민경이 | Vite+React+Tailwind 셋업, SafetyModal·Button·Card·Spinner 공통 컴포넌트, ProfilePage+API 모듈 구현(PR #14·#26·#27) | [→](members/민경이.md#2026-06-02-day-2) |
| 장민수 | 레포 구조 파악, LivePortrait animals 모드 conda 환경 세팅·동작 확인, 파이프라인 README 작성(PR #22) | [→](members/장민수.md#2026-06-02-day-2) |

**팀 전체:** 백엔드 핵심 API 완성 + AI 위기감지·추모 메시지·TTS/평가 골격 + 프론트 기반 구축. 강사님 스크럼(서비스 시나리오 구체화·Gemini 전환) 반영. CI required 승격.

---

## 2026-06-03 (Day 3 — 휴일)

| 이름 | 한 일 (요약) | 상세 |
|------|------------|------|
| 모세종 | PR #28~#32 리뷰·머지, risk_level 0~3·Gemini 실연동·CI AI 의존성 수정(PR #31) | [→](members/모세종.md) |
| 김윤한 | PR #34 반영(PII 제거·router 충돌 해소), llm_log.py 재수정, assess_crisis() 추가, GET /hospitals 카카오맵 API 연동 완료 | [→](members/김윤한.md) |
| 반소람 | Gemini provider.py 연동 완성, 84종 테스트 통과, 백엔드 스키마 키 정렬(PR #29) | [→](members/반소람.md) |
| 정환주 | TTS·평가 골격 테스트 10종, ai/requirements.txt, SETUP TTS 셋업 문서(PR #32) | [→](members/정환주.md) |
| 민경이 | EmotionPage·MessagePage 구현, PR #28 Approve(PR #30) | [→](members/민경이.md#2026-06-03-day-3) |
| 장민수 | — | [→](members/장민수.md) |

**팀 전체:** AI provider.py Gemini 실연동 완료. 프론트 감정·메시지 화면 구현. 로그인(RDB) 필수 요구사항 확인.

---

## 2026-06-04 (Day 4)

| 이름 | 한 일 (요약) | 상세 |
|------|------------|------|
| 모세종 | NCP 실서버 배포(systemd·nginx·GitHub Actions 자동배포), 로그인·미디어 API 구현, 버그 수정 3건, PR #48~#59 관리 | [→](members/모세종.md) |
| 김윤한 | Docker Compose 완성·MongoDB 볼륨 마운트, Gemini API 키 설정, Dockerfile 추가, L1 위기감지 연동, HDD 500GB 마운트 | [→](members/김윤한.md) |
| 반소람 | ⑤ 미션 추천+규칙 풀 확장(30개), ⑦ L1+골든셋 30개 보강, ③ 품질 검증(Gemini 6종 통과), 159종 통과 | [→](members/반소람.md#2026-06-04-day-4) |
| 정환주 | Gemini·Google Cloud TTS 키 발급·실연결, **백엔드 TTS 실연결(PR #40)** — ④ TTS 가짜→진짜, 환경 정합(PR #35), 팀 PR 리뷰 3건(#33·#36·#38), 추모 윤리 경계 정리, PROGRESS 갱신·build_report 핸드오프(PR #58) | [→](members/정환주.md#2026-06-04-day-4) |
| 민경이 | EmotionPage score 매핑·MissionPage·ReportPage·LoginPage·RegisterPage 구현, 실서버 연결 테스트 완료 | [→](members/민경이.md#2026-06-04-day-4) |
| 장민수 | TtsPage·TimelinePage·MediaPage 구현(PR #53), LivePortrait 비전형 동물 7종 검증·추모 강도 0.4 확정(PR #65), 홈서버 HDD 연결 | [→](members/장민수.md#2026-06-04-day-4) |

**팀 전체:** 로그인(RDB) 구현 완료(강사 필수 요구사항). AI·프론트 MVP 8개 기능 완성. NCP 실서버 배포·자동배포 구축. LivePortrait 7종 동물 검증.

---

## 2026-06-05 (Day 5)

| 이름 | 한 일 (요약) | 상세 |
|------|------------|------|
| 모세종 | 서비스 방향 확정(3단계·수의사↔보호자 플랫폼), PERSO 립싱크 2단계 플로우 구현·동물 한계 확인, 4종 비교 실험 설계, 1단계 DB 스키마(PetDiary·Vet·VetAdvice) + PostgreSQL 준비, PR #89~#100 관리 | [→](members/모세종.md#2026-06-05-day-5) |
| 김윤한 | docker-compose 백엔드+MongoDB 통합, DuckDNS 도메인+Let's Encrypt HTTPS 설정, MongoDB 컨테이너 연결 수정(localhost→rainbow_mongo), media upload 검증 수정 PR 제출, 미디어 다운로드 API 추가(PR #111) | [→](members/김윤한.md#2026-06-05-day-5) |
| 반소람 | 위기 차단 보강, 1단계 증상 진료·2단계 장례·3단계 기념일(D+30/D+100) 케어 신규, RAG corpus 56개 확장(장례·미션 신설), memorial RAG retrieve() 연결, RAG A/B 테스트 완료 | [→](members/반소람.md#2026-06-05-day-5) |
| 정환주 | RAG 검색 파이프라인 신설(ChromaDB, PR #79)+검색 품질 실증 도구(Hit@1/MRR), 벡터DB 스터디·비교 문서(PR #73), ④ TTS 음성 다양화·실패 폴백(PR #71·#73), HHHHHMM 척도 모듈(도먼트), PERSO 아바타 핸드오프, 1단계 확장구조 역할분담 | [→](members/정환주.md#2026-06-05-day-5) |
| 민경이 | SymptomsPage 병원 카드·HealthRecordsPage 신규·FuneralPage 신규(장례 안내) 구현, 모바일 반응형 수정, Capacitor Android 앱 전략 확정, PR #84 업데이트 | [→](members/민경이.md#2026-06-05-day-5) |
| 장민수 | `merge_audio()`(PR #74)·driving env 분리(#83)·PERSO 립싱크 검증+이빨 발견(#90·#91)·remote 모드+`server.py`(#95)·GPU 세팅 가이드(#96)·잔잔 driving 템플릿·PERSO 전수조사(Enterprise 1671크레딧) | [→](members/장민수.md#2026-06-05-day-5) |

**팀 전체:** **수의사↔보호자 쌍방향 플랫폼 방향 확정** (병원=웹·보호자=앱). 1단계(건강관리/증상 기록) → 2단계(장례 안내) → 3단계(펫로스 케어) 플로우 + AI RAG few-shot·1인칭 편지 모드 검증 완료. 프론트 1·2단계 신규 화면(SymptomsPage·HealthRecordsPage·FuneralPage) + Android Capacitor 전략 확정. 멀티모달 사진→영상+음성 파이프라인 완성. Docker+HTTPS 인프라 완성.

---

## 2026-06-06 (Day 6)

| 이름 | 한 일 (요약) | 상세 |
|------|------------|------|
| 모세종 | — | [→](members/모세종.md) |
| 김윤한 | — | [→](members/김윤한.md) |
| 반소람 | — | [→](members/반소람.md) |
| 정환주 | — | [→](members/정환주.md) |
| 민경이 | — | [→](members/민경이.md) |
| 장민수 | LivePortrait driving 영상 7종 전수 비교(강아지·고양이·토끼·햄스터), 소스 입 모양·단일 클립이 핵심 발견, 소스 사진 가이드 도출, driving 자동 선택 설계안 정리 → PR #117 | [→](members/장민수.md#2026-06-06-day-6) |

**팀 전체:** 멀티모달 방향 전환(PERSO 드랍 → LivePortrait 채택). driving 영상 비교 실험으로 발화 효과 검증 + 소스 사진 가이드 도출.

---

## 2026-06-08 (Day 8)

| 이름 | 한 일 (요약) | 상세 |
|------|------------|------|
| 모세종 | FEATURE_SPEC 갱신·스크럼 문서 작성, PR #123·#125~#127 머지, 강사 스크럼 반영 SERVICE_FRAME.md 신규 작성, 시한부 선고 진입점 확정, docs 정리(archive+README) → PR #136 | [→](members/모세종.md#2026-06-08-day-8) |
| 김윤한 | L1 응답 스키마 연동(MessageResponse welfare_resources 필드 추가), services/message.py CrisisAction.BLOCK 분기 수정, PR #128 생성·CI 통과·머지·NCP 배포 완료 | [→](members/김윤한.md) |
| 반소람 | (오전) L1/L2/L3 차등 응답 라우팅·복지자원 정리 + (오후) 위기감지 완곡표현 미탐 보강·오탐 방지(애매=L1/명확죽음완곡=L2), memorial 1인칭 가드 부분일치 오탐 수정, 골든셋+10(254→289 통과), funeral 데모 점검, 미션·보상 설계노트 | [→](members/반소람.md#2026-06-08-day-6) |
| 정환주 | TTS 어린아이+감정 음색 탐색 (instruct·EQ 후처리, qwen3_emotion.py·tone_down.py 신규) → PR #134 | [→](members/정환주.md) |
| 민경이 | **프론트 React Native 전환** — Vite+Capacitor → Expo SDK 52, 전체 화면 재구현(13개), 앱 아이콘 교체(레인보우브릿지 일러스트), Expo Go Android 실기기 테스트 완료, Docker 백엔드 연결, PR 제출·머지 (#133) | [→](members/민경이.md#2026-06-08-day-8) |
| 장민수 | remote GPU 테스트(통신·코드 정상, 서버 driving 누락 발견·정환주 핸드오프) + 고정 터널 URL `.env` 기록, XPose 입 개폐 자동선택 검증(5배 분리, PR #120), ETHICS 영상 윤리 PERSO→LivePortrait 갱신(PR #124), 회복게이트 중간보상·저장정책 정리, 영상 톤·강도 실험(ambient~발화, driving 10종 랭킹 d12·d11 최강) | [→](members/장민수.md#2026-06-08-day-8) |

**팀 전체:** 강사 스크럼 — 연계형(B2B2C)·시한부 선고 진입점·왁구 우선 확정. AI 위기 라우팅 L1/L2/L3 완성·머지. 프론트 React Native 전환 완료. 멀티모달: remote 경로 검증·XPose 자동선택 검증·영상 강도 탐색.

---

## 2026-06-09 (Day 9)

| 이름 | 한 일 (요약) | 상세 |
|------|------------|------|
| 모세종 | PR #157~#178 리뷰·머지(22건), 발표 시나리오 스크립트 35분 구조 완성(피벗 슬라이드·시연 영상 피날레), GPU 역할 분리 결정(TTS↔LP 2터널), 장민수 ngrok GPU 가이드 작성, E2E NCP 실서버 통과 확인 | [→](members/모세종.md#2026-06-09-day-9) |
| 김윤한 | TTS Qwen3 GPU 서버 HTTP 연동·Google TTS 폴백 구조(PR #155), play_count + 로그인 접속 로그 추가, build_report play_count·session_count 집계 확장, NCP 재배포·TTS 왕복 테스트 완료 | [→](members/김윤한.md) |
| 반소람 | 미션 회복근거(rationale·5분류↔5이론) 부착 + 미션 풀 30→60 확장, 일상복귀 신호 분석 틀(`recovery_signal`)+발표 시뮬, RAG 사용처 정리(comfort 정리·3곳 확정), 추모(3인칭) 별명 본문 전체 일관 호명 수정 | [→](members/반소람.md) |
| 정환주 | **TTS remote 실연동 검증 성공**(NCP→GPU 왕복: Google폴백 mp3 → 세종 재배포 후 Qwen3 wav 8.5초 전환 확인, ngrok 200 도달) + CLI `--gender man/woman` 수정(PR #162)·GPU_SERVER §12 인계문서(PR #164)·PR #163 리뷰, **LivePortrait 엔진이 정환주 GPU에 미설치 발견** → 영상 = 민수 3060 별도 터널 구조로 결정·ngrok 한도 리스크 분석 | [→](members/정환주.md#2026-06-09-day-9) |
| 민경이 | 봉투 애니메이션 3단계·welfare 섹션·미션 rationale 아이콘, 버킷리스트·일기 신규 화면, 재방문자 AsyncStorage 초기화, 키보드 가림·ForwardRef 에러 수정, 헤더 홈/로그아웃 버튼 추가 | [→](members/민경이.md#2026-06-09-day-9) |
| 장민수 | 펫로스 회복 논문근거 보강(ICG α=0.93·예기비탄·효과크기 g=0.388/0.41·Continuing Bonds 게이트 근거, PR #165), LP 본체가 장민수 PC에만 존재 규명→발표 호스트 **소람 PC 전환**, 소람용 LP 설치 가이드 작성(함정3개·PowerShell호환, PR #171), 발표 사전녹화 백업본 2종 생성·검증(06_backup, 1·3인칭 BGM) | [→](members/장민수.md#2026-06-09-day-9) |

---

## 2026-06-10 (Day 10)

| 이름 | 한 일 (요약) | 상세 |
|------|------------|------|
| 모세종 | PR #206~#212 리뷰·머지, SQLite DB 볼륨 수정(재배포 데이터 유지), 슈퍼 계정 6개 생성·데이터 시딩(gate=open), NCP 재배포, Expo tunnel 대응 | [→](members/모세종.md#2026-06-10-day-10) |
| 김윤한 | MissionResponse category/rationale 필드 추가(PR #207), nginx `/uploads/` 라우팅 수정(TTS 음성 SPA 버그), 장례식장 검색 API 추가(PR #194, 카카오맵), report.py 충돌 해결(PR #186·#187), NCP 컨트롤 타워 운용 | [→](members/김윤한.md) |
| 반소람 | 미션 5분류 논문근거 전부 보강(PubMed/PMC ID·수치), 추모편지 마지막줄 보호자이름 버그 수정, AI 위로편지 완료 확인, 미션 RAG corpus 난이도별 보강(5→15)·난이도 필터 검색 추가·테스트 16통과, RAG 임베딩 키 파싱 버그 수정(쉼표 묶음 키→첫 키, ingest 정상화) | [→](members/반소람.md#2026-06-10-day-8) |
| 정환주 | `report.py` 머지 충돌 해결(접속/재생 지표 병행·additive)·PetResponse 500 수정(테스트 27통과), ④ TTS E2E 음성재생 막힘 진단(원인=NCP nginx `/uploads` 라우팅)→윤한님 수정 후 wav 정상 재검증 | [→](members/정환주.md#2026-06-10-day-10) |
| 민경이 | 홈 생존/이별 모드 분리(BigCard·이별전환모달), 온보딩 프로필 데이터 홈 연동, 신규 가입자 버그 수정, missions·회복 API 경로 수정 | [→](members/민경이.md#2026-06-10-day-10) |
| 장민수 | driving_multiplier 0.4→0.5(PR #188, env 누락 안전망), 중간점검 체크리스트·갭분석 멀티모달 검증·정정(corpus 63건·comfort/vet_protocol 빔·GPU remote 소람PC 2터널 실증·TTS wav 합성 실측검증), 강사 회의록 검토(능동시청 '버튼=play_count' 확정이 우리 구현과 일치), 영상 능동시청 recordPlay 작업→민경이 #198 중복 확인·#200 닫고 dev 정리, photo_selector 입다뭄 미판정 발견(팀 논의 대기) | [→](members/장민수.md#2026-06-10-day-10) |

---

## 2026-06-11 (Day 11)

| 이름 | 한 일 (요약) | 상세 |
|------|------------|------|
| 모세종 | PR #223~#231 리뷰·머지(9건), 슈퍼계정 `@rainbow.dev` gate 영구 fix(PR #227), bong@rainbow.dev 생성, 강사 방향(연구→서비스 완성) 팀 공유 | [→](members/모세종.md#2026-06-11-day-11) |
| 김윤한 | 회복점수 백엔드 연결 `recovery_signal.recovery_score()` + `get_completed_mission_count()`(PR #224), TTS 폴백 로그 status code 추가(PR #232) | [→](members/김윤한.md#2026-06-11-day-11) |
| 반소람 | 자책감 감지→위기 조합 상향(safety.py, 자책 단독 무동작·골든셋 테스트), 미션 수면 질 modifier(5단계→난이도 3축약, 점수 제외·강도 보조), 회복점수·미션·수면·자책 결정 문서 정리, 미션 규칙풀 정리(중복·모호 9건 교체), 미션 문항 검수 가이드 작성→팀원 인계(연락/날씨/자기자비 미션 재검토안 — 실제 수정은 팀원 진행 예정), 신호→점수 치환 갭 식별(Expo Go 실측 범위 검증: 걸음 7일·수면은 dev build 필요→하이브리드), 활동 신호↔활동 미션 양방향 연관 설계, LivePortrait GIF 404 장애 진단(구버전 서버 구동→`/generate/gif` 없음, 재시작으로 해결) | [→](members/반소람.md#2026-06-11-day-9) |
| 정환주 | **PR #228 리뷰 반영: 수면 회복점수서 제외** 결판(결정문서 2개 충돌 표면화→리뷰 수용), 핵심 40/35/25 복원+활동만 add-on, **reviewer가 미션캡 25↔35 불일치 🔴버그 발견→통일+회귀가드**, cross_check 보호자톤 순화, 삼성헬스 RN 실연동 핸드오프(rnhc API 검증), 데모 실증, 58통과·병렬 reviewer+문서검증 에이전트, 공부노트 전영역(다크) | [→](members/정환주.md#2026-06-11-day-11) |
| 민경이 | **Expo SDK 52→54 업그레이드** (강사 요청) — iOS·Android 최신 Expo Go 지원, RN 0.81.5 breaking change 대응(pointerEvents·ImagePicker), 트러블슈팅 문서 신규 작성, 추모 메시지 봉투 미표시 버그 수정(unavailable 폴백 처리) | [→](members/민경이.md#2026-06-11-day-11) |
| 장민수 | 온보딩 화면 신규(onboard.jsx·배경이미지·별 반짝임), 편지 해금 ✉️ 리디자인(다크 네이비·별·흔들림·제목 헤더·Easing, PR #231 dev 머지), LivePortrait 좀비 프로세스 수정(conda run 제거→python.exe 직접호출·Semaphore·Popen wait, 소람님 서버 적용·검증 완료 RAM 92%→34%) | [→](members/장민수.md#2026-06-11-day-11) |

---

## 2026-06-12 (Day 12)

| 이름 | 한 일 (요약) | 상세 |
|------|------------|------|
| 반소람 | 미션 규칙풀 검수 반영(삭제 4·신규 3·카테고리 재분류·난이도 30→15분·전제 미션 graceful화·자책 역효과 완화·글쓰기 11건 메모장 작성 명확화), 이름 조사(받침) 자동 교정 — 추모(memorial)·장례(funeral) 프롬프트의 하드코딩 조사("구름는"·"콩와의") 수정, 장례 고정 안내는 LLM 미경유라 양형+apply_josa 재사용으로 교정, 관련 테스트 108통과 | [→](members/반소람.md#2026-06-12-day-10) |
