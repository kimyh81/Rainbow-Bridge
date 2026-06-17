# 시연영상 TTS 음성 일괄 생성 가이드

> 목적: 시연영상 더빙에 쓸 나레이션·편지 음성을 Qwen3 로컬 GPU TTS로 한 번에 생성한다.
> 담당: 정환주 (`ai/tts/`)
> 작성: 2026-06-17

---

## 1. 개요

시연영상에는 장면별 나레이션과 추모 편지 음성이 필요하다. 매번 손으로 한 줄씩
합성하면 느리고 실수가 생긴다. 그래서 **대본(데이터)** 과 **실행(스크립트)** 을 분리했다.

- 대본만 고치면 음성이 다시 나온다. 코드는 건드릴 필요 없다.
- 백엔드·서버·앱과 무관하다. 순수 로컬 음성 파일 생성이다.
  (앱에서 실시간으로 트는 음성이 아니라, 영상 편집 때 얹는 파일이다.)

---

## 2. 파일 구성

| 파일 | 역할 |
|------|------|
| `ai/tts/scenario_lines.py` | 대본 데이터. `(파일명, tone, 텍스트)` 목록 |
| `ai/tts/synth_scenario.py` | 실행 스크립트. 대본을 읽어 Qwen3로 wav 생성 |
| `ai/tts/qwen3_synthesize.py` | 실제 합성 엔진 (기존 파일). `synthesize()` 제공 |

위 둘(`scenario_lines.py`, `synth_scenario.py`)이 이번에 추가한 파일이고,
`qwen3_synthesize.py`는 원래 있던 합성 함수를 그대로 호출만 한다.

---

## 3. 사전 조건

- **conda 환경 `qwen3-tts`** 가 설치돼 있어야 한다. (torch + Qwen3 의존성 포함)
- **GPU VRAM 약 4.6GB** 필요. webui(포트 8000)나 다른 Qwen3가 떠 있으면
  8GB를 초과해 충돌한다. → **하나만 띄운다.**
- ffmpeg 가 있으면 woman 보이스의 속도 보정(atempo)이 적용된다. 없으면 건너뛴다.

---

## 4. 실행 방법

셸은 cmd / PowerShell / Anaconda Prompt 아무거나 된다. `conda` 가 인식되지
않으면 Anaconda Prompt를 쓴다.

```bash
cd c:\Rainbow_Bridge\Rainbow-Bridge

# 전체 한 번에
conda run --no-capture-output -n qwen3-tts python ai/tts/synth_scenario.py

# 한 줄만 (음질 먼저 확인할 때 권장)
conda run --no-capture-output -n qwen3-tts python ai/tts/synth_scenario.py --only letter_1st
```

- `--no-capture-output` : 진행 로그를 실시간으로 보기 위함.
- `-m` 옵션은 쓰지 않는다. `ai/tts/__init__.py` 가 google-cloud 모듈을 끌어와
  충돌하므로, 스크립트를 **파일 경로로 직접 실행**한다.
- 첫 실행은 GPU 모델 로드로 수십 초 걸린다. 이후 같은 프로세스 안에서는 캐시된다.

### 출력 위치

```
ai/tts/_output/scenario/
  letter_1st.wav      # 1인칭 편지
  letter_3rd.wav      # 3인칭 편지
  s01_narration.wav   # 나레이션
  ...
  closing.wav
```

`_output/` 은 .gitignore 대상이라 git에 올라가지 않는다.

---

## 5. 동작 원리

### 5-1. tone → 보이스 매핑

`scenario_lines.py` 의 각 줄은 `tone` 값으로 목소리를 고른다.
`qwen3_synthesize.py` 가 tone을 고정 화자(seed)로 변환한다.

| tone | 화자 | 용도 |
|------|------|------|
| `girl` | 1인칭 여성 (seed 46286) | 1인칭 편지 |
| `boy` | 1인칭 남성 (seed 29018) | 1인칭 편지(남성) |
| `woman` | 3인칭 나레이션 (seed 21424) | 나레이션·3인칭 편지 |

seed가 화자 ID 역할을 한다. seed를 고정하므로 같은 tone은 항상 같은 목소리가
나온다. (임의 화자 생성이 아니다.)

### 5-2. 합성 흐름

```
synth_scenario.py
  └─ scenario_lines.LINES 를 순회
       └─ 각 줄마다 qwen3_synthesize.synthesize(text, tone, filename)
            ├─ 문장 끝 부호 없으면 마침표 추가 (올림 억양 방지)
            ├─ build_instruct() 로 보이스 지시문 구성
            ├─ seed 고정 후 모델 생성
            ├─ 피크 정규화(-0.5dBFS) + 고역 톤다운(EQ)
            ├─ wav 저장
            └─ atempo 속도 보정 (woman=0.95)
```

### 5-3. 출력 폴더 지정의 함정 (중요)

`qwen3_synthesize.py` 는 **import 시점에** 출력 폴더(`_OUTPUT_DIR`)를 한 번
읽고 고정한다. 그래서 `synth_scenario.py` 는 `qwen3_synthesize` 를 import 하기
**전에** 환경변수 `TTS_OUTPUT_DIR` 를 설정한다.

```python
# import 전에 먼저 설정해야 _output/scenario 로 저장된다
os.environ["TTS_OUTPUT_DIR"] = os.path.join(_BASE, "scenario")
from qwen3_synthesize import synthesize   # 이 줄에서 _OUTPUT_DIR 확정
```

import 이후에 환경변수를 바꿔도 반영되지 않는다. 같은 패턴의 코드를 작성할 때
주의한다.

---

## 6. 대본 수정 방법

`ai/tts/scenario_lines.py` 의 `LINES` 목록만 고친다.

```python
LINES = [
    ("letter_1st", "girl", _LETTER_1ST),   # (파일명, tone, 텍스트)
    ("s01_narration", "woman", "..."),
    ...
]
```

- **파일명**: 출력 wav 이름이 된다. 영문/숫자/언더스코어 권장.
- **tone**: `girl` / `boy` / `woman` 중 하나.
- **텍스트**: 낭독할 내용. 긴 편지는 삼중따옴표 문자열로 둔다.

특정 줄만 다시 뽑을 때는 `--only <파일명>` 을 쓴다.

---

## 7. 주의사항

### 7-1. 긴 텍스트
`synthesize()` 는 `max_new_tokens=3072` (약 1500자·255초)로 상한이 걸려 있다.
추모 편지(400~500자)는 한 번에 처리된다. 그 이상으로 길어지면 잘릴 수 있으니
문단을 나눠 별도 줄로 만든다.

### 7-2. 줄바꿈·문장부호
편지처럼 줄바꿈이 많은 텍스트는 모델이 문단 사이 호흡을 어떻게 읽는지
**들어보고 조정**한다. 어색하면 줄바꿈을 마침표나 공백으로 바꾼다.

### 7-3. 1인칭 편지 윤리 (필수)
1인칭 편지(`letter_1st`)는 반려동물 화법이다. 루트 `CLAUDE.md` §1 기준,
다음 조건에서만 노출한다.

- 보호자 동의
- 경고 문구 표시: "AI가 보호자가 전해준 추억을 바탕으로 재해석한 꿈 속 작별 인사입니다."
- risk_level 0

시연영상에 1인칭 편지를 쓸 때는 **경고 문구를 화면에 함께** 넣는다.

---

## 8. 다음 단계 — 영상에 합치기

생성된 wav를 영상 편집툴(프리미어, 캡컷 등)에서 각 장면에 얹는다.
명령줄로 붙이려면 ffmpeg를 쓴다. 예시(영상에 오디오 입히기):

```bash
ffmpeg -i scene06.mp4 -i ai/tts/_output/scenario/letter_1st.wav \
       -c:v copy -map 0:v:0 -map 1:a:0 -shortest scene06_voiced.mp4
```

---

## 9. 트러블슈팅

| 증상 | 원인 | 조치 |
|------|------|------|
| `conda : 명령을 찾을 수 없습니다` | conda 미초기화 | Anaconda Prompt에서 실행 |
| CUDA out of memory | webui 등 다른 Qwen3 동시 구동 | 하나만 띄운다 |
| wav가 `_output` 바로 밑에 생김 | import 순서 문제 (5-3) | env를 import 전에 설정했는지 확인 |
| 음성이 잘림 | 텍스트가 1500자 초과 | 문단을 나눠 별도 줄로 |
| 첫 실행이 오래 걸림 | 모델 로드(정상) | 수십 초 대기 |

---

## 10. 관련 파일

- 합성 엔진: `ai/tts/qwen3_synthesize.py` (`synthesize`, `AVAILABLE_VOICES`)
- 보이스 설계 기록: `ai/tts/PROTOTYPE_VOICE.md`
- 톤 매핑 규칙: `ai/tts/CLAUDE.md` §3
- 윤리 경계: 루트 `CLAUDE.md` §1, `ai/CLAUDE.md` §0
