# 핸드오프 — 삼성헬스 헬스데이터 형식·스키마 (반소람 공유)

> 정환주 → 반소람 · 2026-06-12
> **목적:** 객관 수면·활동 데이터가 **어떤 형식으로 들어와서 어떤 스키마로 나오는지** 공유.
> 소람 로직(미션·메시지)에서 가져다 쓸 수 있게 입력 형식·출력 키를 명시합니다.

---

## 1. 핵심 — 어디서 오든 출력은 **하나**

데이터 경로는 둘이지만 **출력 dict는 동일**합니다. 소람은 이 출력만 보면 됩니다.

```python
{"steps": int | None, "sleep_hours": float | None}
```

| 경로 | 함수 | 입력 |
|------|------|------|
| 실시간(RN 개발빌드) | `from_health_connect(steps_result, sleep_result)` | Health Connect readRecords JSON |
| 백업(export, 폰 불필요) | `from_samsung_export(steps_csv, sleep_csv, date=)` | 삼성헬스 export CSV 텍스트 |

```python
from ai.evaluation.health_export_adapter import from_samsung_export
out = from_samsung_export(step_csv_text, sleep_csv_text, date="2026-06-11")
# → {"steps": 9092, "sleep_hours": 7.5}
```

---

## 2. export CSV 형식 (실 export 2026-06-12 검증)

- zip 파일명: `samsunghealth_<id>_<timestamp>.zip`
- **공통 구조:** 1행=메타(`com.samsung.shealth.X,버전,N`) → 2행=**헤더** → 3행~ 데이터
  (파서가 헤더 자동 탐지하므로 메타행은 신경 안 써도 됨)

| 데이터 | 파일명 | 핵심 컬럼 | 형식 |
|--------|--------|-----------|------|
| 걸음 | `com.samsung.shealth.step_daily_trend.*.csv` | `count` / `day_time` | 걸음수(int) / epoch ms |
| 수면 | `com.samsung.shealth.sleep.*.csv` | `com.samsung.health.sleep.start_time` / `...end_time` | datetime 문자열 |

> ⚠️ 수면 컬럼은 파일명은 `shealth.sleep`인데 **헤더 컬럼명은 `health.sleep`**(s 없음). 파서에 둘 다 후보로 넣어둠.
> ⚠️ 걸음은 **하루치만** 넘기거나 `date=` 로 걸러야 함(파서가 무조건 합산 → 여러 날이면 과대).

---

## 3. 저장 스키마 — `health_logs` (MongoDB)

`POST /api/v1/health/sync` 가 날짜별 1건 upsert. `GET /report` 가 최근 1건을 읽어 점수에 반영.

```python
{"pet_id": str, "date": "YYYY-MM-DD", "steps": int|None, "sleep_hours": float|None, "synced_at": datetime}
```

---

## 4. 점수·컨디션 출력 스키마 (`recovery_signal`)

`GET /report` 응답 `recovery_signal` 안에 실리는 헬스 관련 키:

```python
{
  "recovery_index": int,        # 0~100. 활동(걸음) 들어오면 +10 반영. 수면은 제외.
  "scoring": "base" | "blend",  # 활동 반영 여부
  "activity_score": float|None, # 걸음 0~100
  "sleep_score": float|None,    # 수면 0~100 (점수엔 미반영, 표시·교차검증용)
  "cross_check": {              # 객관 수면 vs 주관 감정
      "status": "mismatch_high_risk" | "mismatch" | "agree_low" | "agree_ok" | "unknown",
      "mismatch": bool,
      "note": str|None          # 보호자 노출용 비낙인 문장
  },
  "condition": {                # 오늘 컨디션 추정(회복점수와 별개)
      "condition": "양호" | "주의" | "보통",
      "confidence": "높음" | "낮음"
  } | None
}
```

---

## 5. 수면 "두 트랙" — 소람 영역 주의 ★

이름만 같은 수면이 **별개 두 트랙**입니다. 섞지 마세요.

| 트랙 | 데이터 | 용도 | 담당 |
|------|--------|------|------|
| **객관 수면시간** (본 문서) | `sleep_hours` (삼성헬스) | 교차검증·컨디션·표시 | 정환주 |
| **주관 수면질 5단계** | `sleep_quality` 1~5 (체크인) | **미션 난이도 보조** | **반소람**(modifier)·모세종(스키마)·민경이(UI) |

- 둘 다 **회복점수 산식엔 제외**.
- 소람이 객관 데이터(`steps`/`sleep_hours`/`cross_check`/`condition`)를 **미션·메시지 로직에 쓰고 싶으면** 위 4번 출력을 그대로 가져다 쓰면 됩니다(예: `condition=="주의"`면 가벼운 미션 우선 등 — 설계는 소람 판단).
- 주관 5단계 미션 modifier(`_apply_sleep`)는 이미 소람 영역에 있고, 현재 백엔드에서 `sleep_quality`가 안 넘어오는 **끊긴 고리**가 있음(create_default_missions·Redis 캐시). 이건 별도 이슈.

---

## 6. 코드 위치

- 어댑터: `ai/evaluation/health_adapter.py`(실시간) · `health_export_adapter.py`(export)
- 점수·컨디션: `ai/evaluation/health_signal.py` · `recovery_signal.py`
- 백엔드: `backend/app/api/v1/endpoints/health.py`(/sync) · `services/report.py`(get_report 배선)
- 테스트: `ai/evaluation/tests/test_health_*` · `backend/tests/test_report_service.py`

질문 있으면 정환주에게.
