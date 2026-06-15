"""⑧-확장: 휴대폰 사용 지표 → '관찰 문장' (2단계 · LLM팀) — 로직.

파이프라인:
    1단계(세종 PM 수집기) → **비식별 일별 카테고리 로그**(raw 패키지명 X)
        [{"date": "2026-06-12", "category": "EDUCATION", "minutes": 5,
          "late_night_minutes": 0}, ...]
        # 카테고리 4종: ENTERTAINMENT / SOCIAL / EDUCATION / FINANCE
    1.5단계 어댑터(summarize_category_logs) → 요약 지표
        {"night_usage": {"today": 57, "avg7": 18},
         "education_usage": {"today": 5, "avg7": 40}}
    2단계(analyze_usage) → 관찰 문장
        "최근 일주일 평균 대비 새벽 활동이 증가했습니다."
        "최근 일주일 평균 대비 교육 관련 앱 사용이 감소했습니다."

    이미 today/avg7 로 집계해 주면 어댑터를 건너뛰고 analyze_usage 에 바로 넣어도 됩니다.

설계(memorial·mission 과 같은 '주입(generate) + 가드 + 폴백' 패턴):
    today vs avg7 비교로 **방향(증가/감소/유지)을 코드가 확정**(=정본) →
    LLM 이 있으면 문장만 다듬고(방향·금칙어 가드) → 실패/이상 출력이면
    규칙 문장으로 조용히 폴백(graceful). 단말·키 없이도 항상 문장이 나옵니다.

⚠️ 경계 (../evaluation/phone_usage.py advisory 원칙과 동일):
   - **의학적 진단·추측 금지.** 관찰된 변화 사실만. 방향을 LLM 자유 생성에 맡기지
     않으므로 "추측 금지"가 코드로 보장됩니다.
   - 위기(1393)·crisis 자동 트리거 금지 — 이 문장은 '관찰' 까지만.

cf. 같은 데이터의 **정량 신호**(위축·리듬 교란 등)는 ../evaluation/phone_usage.py
    (정환주). 여기는 그 위에 얹는 **자연어 관찰 문장** 레이어(반소람)입니다.
"""

from __future__ import annotations

import json
from datetime import date
from typing import Any, Final, Optional, Protocol

from .prompts import usage_observation as prompt_mod


class GenerateFn(Protocol):
    """provider.generate 와 맞춘 호출 시그니처 (주입용)."""

    def __call__(
        self,
        prompt: str,
        *,
        max_tokens: int = 256,
        temperature: float = 0.3,
        json_mode: bool = False,
    ) -> str: ...


# 생성 파라미터 — 관찰 문장은 창의성보다 일관성이 중요해 온도 낮게.
_MAX_TOKENS: Final = 256
_TEMPERATURE: Final = 0.3

# '변화 없음(유지)' 데드존 — 잡음 같은 미세 변화를 과대 해석하지 않도록.
# 절대 5분 이상 그리고 7일 평균 대비 15% 이상일 때만 증가/감소로 봅니다.
_CHANGE_MIN_MINUTES: Final = 5.0
_CHANGE_MIN_RATIO: Final = 0.15

# avg7 = '오늘 제외' 직전 며칠의 일평균(기본 7일). 스크린샷의 '7일 평균'.
_AVG_WINDOW_DAYS: Final = 7

# LLM 문장 가드 — 진단·추측을 암시하는 표현이 섞이면 규칙 문장으로 폴백.
_FORBIDDEN: Final[tuple[str, ...]] = (
    "우울", "불안", "질환", "장애", "진단", "병", "증상",
    "아마", "추정", "보입니다", "보여집니다", "듯", "우려", "위험",
    "것같", "지도모", "수도있",
)


def _direction(today: float, avg7: float) -> str:
    """today vs avg7 → 증가/감소/유지 (데드존 적용)."""
    delta = today - avg7
    if abs(delta) < _CHANGE_MIN_MINUTES:
        return "유지"
    if avg7 > 0 and abs(delta) < avg7 * _CHANGE_MIN_RATIO:
        return "유지"
    return "증가" if delta > 0 else "감소"


def _josa_iga(word: str) -> str:
    """단어 받침 유무로 주격조사 이/가 선택(한글 음절만 판별, 그 외 '이')."""
    if not word:
        return "이"
    last = word[-1]
    if "가" <= last <= "힣":
        return "이" if (ord(last) - 0xAC00) % 28 else "가"
    return "이"


def _rule_sentence(label: str, direction: str) -> str:
    """방향만으로 만드는 결정론적 관찰 문장(폴백·정본)."""
    josa = _josa_iga(label)
    if direction == "유지":
        return f"최근 일주일 평균 대비 {label}{josa} 비슷한 수준을 유지하고 있습니다."
    move = "증가" if direction == "증가" else "감소"
    return f"최근 일주일 평균 대비 {label}{josa} {move}했습니다."


def _to_float(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_day(token: Any) -> Optional[date]:
    try:
        return date.fromisoformat(str(token)[:10])
    except (ValueError, TypeError):
        return None


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def summarize_category_logs(
    logs: list[dict[str, Any]],
    *,
    as_of: Optional[date] = None,
    window_days: int = _AVG_WINDOW_DAYS,
    night_key: str = "night_usage",
) -> dict[str, dict[str, float]]:
    """세종 PM 수집기의 **일별 카테고리 로그(비식별)** → analyze_usage 입력 요약.

    1단계 수집기가 패키지명을 제거하고 카테고리로 집계해 보내는 형태를 받아,
    '오늘(today)' 과 '직전 N일 평균(avg7)' 으로 요약합니다. raw 패키지명은
    아예 들어오지 않으므로 익명화는 수집기 단계에서 끝나 있습니다.

    Args:
        logs: 일별·카테고리별 기록. 한 건:
            ``{"date": "2026-06-12", "category": "ENTERTAINMENT",
               "minutes": 234, "late_night_minutes": 56}``.
            카테고리는 대소문자 무관(내부에서 소문자화). 같은 날 같은 카테고리가
            여러 건이면 합산합니다.
        as_of: '오늘'로 볼 기준일. None 이면 로그의 **최신 날짜**.
        window_days: avg7 산정 창(일). 기본 7 — 오늘 **제외** 직전 7일의 일평균.
        night_key: 새벽 합산 지표의 key(기본 ``night_usage``).

    Returns:
        ``{"<카테고리소문자>_usage": {"today", "avg7"}, "night_usage": {...}}``.
        ``night_usage`` 는 전 카테고리 ``late_night_minutes`` 합(시간대 신호).
        ⚠️ 직전 N일에 관측 데이터가 없으면(예: 첫날·하루치만 수집) 빈 dict —
        추세를 보려면 며칠치가 쌓여야 합니다(graceful).
    """
    per_day_cat: dict[date, dict[str, float]] = {}
    per_day_night: dict[date, float] = {}
    for rec in logs:
        day = _parse_day(rec.get("date"))
        if day is None:
            continue
        cat = str(rec.get("category") or "").strip().lower()
        if cat:
            bucket = per_day_cat.setdefault(day, {})
            bucket[cat] = bucket.get(cat, 0.0) + (_to_float(rec.get("minutes")) or 0.0)
        per_day_night[day] = per_day_night.get(day, 0.0) + (
            _to_float(rec.get("late_night_minutes")) or 0.0
        )

    days = sorted(set(per_day_cat) | set(per_day_night))
    if not days:
        return {}
    today_day = as_of or days[-1]
    # 오늘 제외, 직전 window_days 일 중 '관측된' 날들(수집 안 된 날은 평균에서 제외).
    past = [d for d in days if 0 < (today_day - d).days <= window_days]
    if not past:
        return {}

    metrics: dict[str, dict[str, float]] = {}
    # 새벽 사용(전 카테고리 합) — 시간대 신호.
    metrics[night_key] = {
        "today": round(per_day_night.get(today_day, 0.0), 1),
        "avg7": round(_mean([per_day_night.get(d, 0.0) for d in past]), 1),
    }
    # 카테고리별.
    categories: set[str] = set(per_day_cat.get(today_day, {}))
    for d in past:
        categories |= set(per_day_cat.get(d, {}))
    for cat in sorted(categories):
        today_val = per_day_cat.get(today_day, {}).get(cat, 0.0)
        avg_val = _mean([per_day_cat.get(d, {}).get(cat, 0.0) for d in past])
        metrics[f"{cat}_usage"] = {"today": round(today_val, 1), "avg7": round(avg_val, 1)}
    return metrics


def _build_findings(
    metrics: dict[str, Any], labels: dict[str, str]
) -> list[dict[str, Any]]:
    """입력 지표(dict)를 지표별 결과로. today/avg7 이 없거나 숫자가 아니면 건너뜀."""
    findings: list[dict[str, Any]] = []
    for key, value in metrics.items():
        if not isinstance(value, dict):
            continue
        today = _to_float(value.get("today"))
        avg7 = _to_float(value.get("avg7"))
        if today is None or avg7 is None:
            continue
        findings.append(
            {
                "key": key,
                "label": labels.get(key, key),
                "today": today,
                "avg7": avg7,
                "delta": round(today - avg7, 1),
                "direction": _direction(today, avg7),
            }
        )
    return findings


def _sentence_ok(sentence: str, direction: str) -> bool:
    """LLM 문장 가드: 금칙어 없음 + 방향이 정본과 일치(추측·반전 방지)."""
    if not sentence or any(bad in sentence for bad in _FORBIDDEN):
        return False
    if direction == "증가":
        return "증가" in sentence or "늘" in sentence
    if direction == "감소":
        return "감소" in sentence or "줄" in sentence
    return "유지" in sentence or "비슷" in sentence  # 유지


def _parse_llm(raw: str) -> dict[str, str]:
    """LLM JSON({observations:[{key,sentence}]}) → {key: sentence}. 깨지면 빈 dict."""
    data = json.loads(raw)
    items = data.get("observations") if isinstance(data, dict) else data
    if not isinstance(items, list):
        return {}
    out: dict[str, str] = {}
    for it in items:
        if isinstance(it, dict) and it.get("key"):
            out[str(it["key"])] = str(it.get("sentence", "")).strip()
    return out


def analyze_usage(
    metrics: dict[str, Any],
    *,
    labels: Optional[dict[str, str]] = None,
    generate: Optional[GenerateFn] = None,
) -> dict[str, Any]:
    """사용 지표(1단계 수집기 출력)에서 관찰 문장(2단계)을 만듭니다.

    Args:
        metrics: 지표별 ``{"today": <분>, "avg7": <분>}`` 묶음.
            예: ``{"night_usage": {"today": 57, "avg7": 18},
                   "education_usage": {"today": 5, "avg7": 40}}``.
            today/avg7 이 없거나 숫자가 아닌 지표는 조용히 건너뜁니다(graceful).
        labels: 지표 key → 한국어 라벨 덮어쓰기(선택). 없으면 prompts 의
            DEFAULT_LABELS, 그래도 없으면 key 그대로.
        generate: LLM 호출 함수(provider.generate). None 이면 규칙 문장만 사용.
            주입돼도 실패/이상 출력이면 규칙 문장으로 폴백(방향은 항상 코드가 정함).

    Returns:
        ``{"observations": [문장, ...], "findings": [...], "source": "llm"|"rule"|"none"}``.
        ``observations`` 는 화면에 그대로 노출 가능한 관찰 문장.
        ``findings`` 는 지표별 ``{key,label,today,avg7,delta,direction}`` 근거.
    """
    label_map = {**prompt_mod.DEFAULT_LABELS, **(labels or {})}
    findings = _build_findings(metrics, label_map)
    if not findings:
        return {"observations": [], "findings": [], "source": "none"}

    # LLM 문장(있으면) — key 별로 가드 통과한 것만 채택.
    llm_sentences: dict[str, str] = {}
    if generate is not None:
        try:
            raw = generate(
                prompt_mod.build_prompt(findings),
                max_tokens=_MAX_TOKENS,
                temperature=_TEMPERATURE,
                json_mode=True,
            )
            llm_sentences = _parse_llm(raw)
        except Exception:  # noqa: BLE001 — 추론 실패는 규칙 폴백으로 흡수(graceful)
            llm_sentences = {}

    observations: list[str] = []
    used_llm = False
    for f in findings:
        cand = llm_sentences.get(f["key"], "")
        if cand and _sentence_ok(cand, f["direction"]):
            observations.append(cand)
            used_llm = True
        else:
            observations.append(_rule_sentence(f["label"], f["direction"]))

    return {
        "observations": observations,
        "findings": findings,
        "source": "llm" if used_llm else "rule",
    }
