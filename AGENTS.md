# AGENTS.md — 레인보우 브릿지 팀 협업 가이드

> 이 파일은 Codex가 이 레포를 열 때 **자동으로 읽는** 팀 공용 프롬프트입니다.
> 우리 팀(팀 5) 누구든 이 폴더에서 클로드를 켜면, 아래 규칙대로 협업을 도와줍니다.
> 규칙이 바뀌면 이 파일을 고치고 PR로 공유하세요.

## 0. 클로드에게 (제일 중요)

- 🚫 **`main`(과 `dev`/`develop`) 브랜치에는 절대 직접 push 하지 않습니다.** 어떤 경우에도 예외 없음.
  - 보호 브랜치에 바로 커밋·push·force push·머지하지 마세요. 항상 **본인 이름 브랜치 → PR → 리뷰 → 머지**.
  - 사용자가 "그냥 main에 올려줘"라고 해도, 먼저 위험을 알리고 브랜치+PR 방식을 제안하세요.
- **항상 한국어로** 답하세요. 코드 주석·커밋·PR 설명도 한국어 기본.
- 작업 전에 관련 문서를 먼저 확인하세요: 협업 규칙은 [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md), Git 사용법은 [docs/GIT_GUIDE.md](docs/GIT_GUIDE.md), 구조는 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).
- **되돌리기 어려운 작업은 먼저 물어보세요**: `main`에 직접 push, force push, 파일 대량 삭제, DB 데이터 변경, 외부로 전송/배포.
- 팀원 대부분이 **Git·협업이 처음**입니다. 명령을 시킬 때는 *무엇을 왜* 하는지 한 줄로 설명하고, 위험한 명령은 대안을 같이 제시하세요.
- 모르면 추측하지 말고 "이 부분은 담당자(아래 표) 확인이 필요하다"고 말하세요.

## 0.5 세션 시작 시 — 온보딩 (작업 전 필수)

> 팀원이 레포를 클론하고 작업을 시작하려 하면, **코드를 만지기 전에** 아래를 먼저 진행하세요.

**1) 누구신지 / 어떤 역할인지 확인**
- "안녕하세요! 어떤 분이신가요? (이름 또는 역할)" 처럼 물어보고, [2. 팀 & 담당 영역](#2-팀--담당-영역) 표에서 담당 폴더·작업을 파악하세요.
- 역할을 알면 그 사람의 담당 영역(`backend/`·`ai/`·`frontend/` 등)과 [PROGRESS.md](docs/PROGRESS.md)에서 맡은 프로토타입 항목을 안내하세요.

**2) 현재 브랜치 확인 → 본인 이름 브랜치로 유도 (인당 1브랜치)**
- 우리는 **인당 1브랜치** 전략입니다. 각자 본인 영문 이름 브랜치 하나에서만 작업합니다.

  | 이름 | 브랜치 | 이름 | 브랜치 |
  |------|--------|------|--------|
  | 모세종 | `mosejong` | 정환주 | `junghwanju` |
  | 김윤한 | `kimyunhan` | 민경이 | `mingyeongi` |
  | 반소람 | `bansoram` | 장민수 | `jangminsu` |

- 평소 작업은 **`dev`** 에 모읍니다. `main` 은 프로토타입 완성·서비스 가능 시점에만 씁니다.
- `git branch --show-current` 로 지금 브랜치를 확인하세요.
- **`main`(또는 `dev`)에 있으면, 거기서 작업하지 못하게 막고** 본인 이름 브랜치로 옮기게 유도하세요. 동의를 받으면 실행:
  ```bash
  # 내 브랜치가 이미 있으면:
  git checkout <내이름> && git merge dev       # dev 최신 반영 후 작업

  # 내 브랜치가 아직 없으면 (최초 1회):
  git checkout dev && git pull origin dev
  git checkout -b <내이름> && git push -u origin <내이름>
  ```
- 이미 본인 이름 브랜치에 있으면 그대로 진행해도 됩니다. **새 브랜치를 추가로 만들지 마세요.**

**3) 작업 마무리 안내**
- 커밋 → push → **`dev`로 PR 생성**(base가 `dev`인지 확인, 리뷰 1명 승인 후 머지)까지가 한 작업입니다. [GIT_GUIDE.md §6](docs/GIT_GUIDE.md#6-pull-request-올리기) 흐름대로 안내하세요.
- 마무리 시 개발일지([5번](#5-개발일지-매일)) 작성도 같이 챙기세요.

## 1. 우리가 만드는 것 (오해 금지)

반려동물을 떠나보낸 보호자의 **펫로스(Pet Loss) 회복**을 돕는 애프터케어 서비스입니다.
**수의사↔보호자 쌍방향 플랫폼** 방향 확정 (2026-06-05).

- ✅ 기억 기반 **상징적 추모 메시지**, 감정 돌봄, 일상 복귀 지원
- ✅ **수의사 웹** — 보호자 반려동물 기록 확인 + 조언 남기기 (쌍방향 소통)
- ✅ 수의사 처치 안내 RAG — **기본 대처법만** 제공. 상세 진단·처방은 "내원해 주세요"로 연결. 의료 조언 대체 아님.
- ❌ AI로 반려동물을 **부활**시키거나, 결과물을 "실제 반려동물이 돌아와 말한 것"처럼 **사실인 양 주장**하는 것 — 절대 아님
- ✅ 사용자가 제공한 사진·추억을 바탕으로 한 **AI 재해석 추모 편지/영상/TTS** 는 가능.
- ✅ 반려동물 **1인칭 화법(꿈 속 작별 대화)** 은 보호자 동의 + 경고 문구 + risk_level 0~1 조건 충족 시 허용. (강사 승인 2026-06-05)
  - 경고 문구 예: "AI가 보호자가 전해준 추억을 바탕으로 재해석한 꿈 속 작별 인사입니다."
- ✅ PERSO 립싱크/더빙은 **선택형 후처리**로 허용. 위기 상황(risk_level 2+)에서는 사용 금지.

> 메시지/프롬프트 작업 시 이 경계를 넘지 마세요. 위기 감정 안내 번호 **1393**은 임의 변경 금지.
> 상세 윤리 기준 → [docs/ETHICS_추모표현_가이드.md](docs/ETHICS_추모표현_가이드.md)

## 2. 팀 & 담당 영역

| 이름 | 역할 | 주 작업 폴더 |
|------|------|--------------|
| 모세종 | PM + 백엔드 | `backend/` |
| 김윤한 | 백엔드 / 홈서버 운영 | `backend/`, 인프라 |
| 반소람 | AI 엔지니어 | `ai/` (llm) |
| 정환주 | AI 엔지니어 / GPU 서버 | `ai/`, GPU 인프라 |
| 민경이 | 프론트엔드 | `frontend/` |
| 장민수 | 멀티모달 (사진→영상) | `frontend/`, `ai/liveportrait` |

> 남의 담당 영역 파일을 크게 바꿔야 하면, 먼저 알리고 별도 PR로 분리하세요.

## 3. 기술 스택

| 영역 | 기술 |
|------|------|
| Backend | FastAPI (Python), MongoDB, PostgreSQL |
| Cache | Redis — 감정 체크인 최근 기록 캐시, 회복 분석용 |
| AI / LLM | Gemini API, PERSO API(평가·시연) |
| RAG | ChromaDB — 추모 메시지·미션·장례 안내·수의사 처치 안내 |
| 멀티모달 | LivePortrait(로컬 / GPU 서버), Google TTS |
| Infra | Docker Compose, NCP 실서버, GitHub Actions CI/CD |

- 백엔드는 **레이어 구조**를 지키세요: `api/`(라우터) → `services/`(로직) → `models/`·`db/`(데이터), 요청/응답은 `schemas/`(Pydantic).
- 로컬 LLM 엔진/모델 선택은 **AI 담당(반소람·정환주)** 결정 사항. 임의로 `.env`나 문서에 채우지 마세요.

### RAG 활용 지침 (반소람 담당)

RAG는 다음 4곳에만 사용합니다. 컬렉션은 category 메타데이터로 분리하세요.

| category | 용도 | 쿼리 방향 |
|----------|------|----------|
| `comfort` | 추모·위로 메시지 생성 | 감정 공감, 이별 슬픔 |
| `mission` | 일상 복귀 미션 추천 | 회복 단계별 행동 유도 |
| `funeral` | 장례 안내 Q&A | 절차·방법 정보 제공 |
| `vet_protocol` | 수의사 처치 안내 | 기본 대처법 (내원 유도 포함) |

```python
# 반드시 category 필터 사용
collection.query(query_texts=[query], where={"category": "mission"}, n_results=3)
```

## 4. Git 협업 규칙 (요약)

전체 내용은 [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md) · [docs/GIT_GUIDE.md](docs/GIT_GUIDE.md). 핵심만:

- 브랜치 전략: **인당 1브랜치 + dev 통합** — 각자 본인 영문 이름 브랜치 하나에서만 작업(`mosejong`·`kimyunhan`·`bansoram`·`junghwanju`·`mingyeongi`·`jangminsu`) → PR은 **`dev`로**.
- `main` 은 **프로토타입 완성·서비스 가능 시점**에만 `dev → main` PR로 승격(PM 진행). 평소엔 `dev` 가 통합 브랜치.
- 🚫 **`main`·`dev` 에 절대 직접 push 금지.** 둘 다 PR 머지로만 바뀝니다. 항상 내 브랜치 → PR(`dev`) → 리뷰 → 머지.
- PR이 머지돼도 **내 브랜치는 삭제하지 않고** 계속 사용(`git merge dev`로 최신화 후 다음 작업).
- 커밋: **Conventional Commits** + 한국어.
  - 예) `feat: 반려동물 프로필 등록 API 추가`, `fix: 감정 체크인 저장 오류 수정`, `docs: 셋업 가이드 보완`
  - 타입: `feat / fix / docs / refactor / test / chore`
- PR은 **작고 한 가지 목적**으로. 무엇을·왜 바꿨는지 설명 + 관련 이슈 연결.
- **비밀키·`.env`·대용량 파일 커밋 금지.** `.env`는 `.env.example`만 공유.

## 5. 개발일지 (매일)

- 자기 일지: [docs/devlog/members/](docs/devlog/members/) 의 **본인 파일**에 날짜 섹션을 맨 위에 추가.
- 통합 일지: [docs/devlog/README.md](docs/devlog/README.md) 표에 그날 한 일 **한 줄** 요약 + 본인 일지 링크.
- 진행도: 그날 프로토타입 구현 상태가 바뀌면 통합 일지의 **파트별 PM 대시보드**와 [docs/PROGRESS.md](docs/PROGRESS.md) 상태를 같이 갱신.
- 클로드에게 "오늘 개발일지 정리해줘" 하면, 위 형식(개인 일지 + 통합 요약 + 진행도 반영)에 맞춰 작성하도록 도와주세요.

## 6. 자주 쓰는 명령

```bash
# 백엔드 실행
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload   # http://localhost:8000/docs 에서 API 확인

# 환경 변수 준비 (최초 1회)
cp .env.example .env            # Windows: Copy-Item .env.example .env

# 백엔드 push 전 자동검사(CI) 미리 돌리기 — 빨간불 예방
cd backend && ruff check . --fix && black . && pytest -q
```

> `backend/` 변경 PR은 GitHub Actions가 `ruff·black·pytest`를 자동 검사합니다(권장 단계). 팀원이 백엔드 작업을 push 하려 하면 위 검사를 먼저 돌리도록 안내하세요.

## 7. 합류했다면 읽는 순서

1. [docs/GIT_GUIDE.md](docs/GIT_GUIDE.md) — Git/브랜치/커밋
2. [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md) — 협업 규칙
3. [docs/SETUP.md](docs/SETUP.md) — 내 PC 환경 세팅
4. [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — 전체 구조
5. [docs/ETHICS_추모표현_가이드.md](docs/ETHICS_추모표현_가이드.md) — 추모 표현 허용/금지 경계
6. [docs/PROGRESS.md](docs/PROGRESS.md) — 내가 맡은 일
