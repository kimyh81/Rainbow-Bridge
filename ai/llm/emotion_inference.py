"""감정 RAG 추론 — background 신호로 감정 체크인 점수(1~10)를 추론합니다.

2026-06-12 설계 확정(모세종 PM):
    ① 입력 = **이미 집계된 신호**만 (PII 안전):
        - `recovery_signal.condition`  ({"condition": "양호"|"주의"|"보통",
          "confidence": "높음"|"낮음"} | None — 정환주 헬스데이터, null 가능)
        - `recovery_signal.cross_check` (센서-자기인식 교차검증)
        - `phone_usage` 분석 결과(`ai/evaluation/phone_usage.analyze_phone_usage`)의
          `concern_level`(0~2)
        - 미션 완료율(0~1)
       일기·편지 같은 원문 텍스트는 입력에 넣지 않습니다(PII).
    ② 출력 = emotion_score **1~10** (기존 체크인 `score`와 동일 스케일).
    ③ 체크인 재정의 = 이 함수가 **매일** 호출되어 그 결과가 그 날의 감정
       체크인(emotion_checkin)이 됩니다. 꾸준함(`recovery_signal._consistency`)은
       이제 미션 완료일 기준이라 이 변경과 독립적입니다.
    ④ RAG 코퍼스 없음 — 규칙(점수·근거 확정) + LLM(표현만, 선택).

설계 패턴은 `usage_observation.py`와 동일합니다:
    점수·등급·근거 문장은 **코드가 확정**(정본) → LLM이 있으면 그 등급을 뒤집지
    않는 선에서 관찰 문장 하나만 다듬고(가드) → 실패/위반 시 규칙 문장으로 조용히
    폴백(graceful). **점수 자체는 LLM이 절대 바꾸지 않습니다** — 회복 게이트·
    1인칭 편지 허용 여부에 쓰이는 안전 민감 값이라 결정론을 유지합니다.

⚠️ `sleep_score`/`activity_score`는 이미 `condition`에 반영되어 있어 별도
   입력으로 받지 않습니다(이중 반영 방지). `condition`이 null이면(체크인<3 또는
   수면데이터 없음) 그 항목 기여는 0으로 graceful 처리합니다.
"""

from __future__ import annotations

import json
from typing import Any, Optional, Protocol

from .prompts import emotion_inference as prompt_mod


class GenerateFn(Protocol):
    """provider.generate 와 맞춘 호출 시그니처 (주입용)."""

    def __call__(
        self,
        prompt: str,
        *,
        max_tokens: int = 200,
        temperature: float = 0.3,
        json_mode: bool = False,
    ) -> str: ...


# 생성 파라미터 — 관찰 문장은 창의성보다 일관성이 중요해 온도 낮게.
_MAX_TOKENS = 200
_TEMPERATURE = 0.3

_BASELINE = 5.0  # 배경 신호가 전혀 없을 때의 중립값
_MIN_SCORE = 1
_MAX_SCORE = 10

# condition (양호/주의/보통) × confidence (높음/낮음) → 점수 보정.
_CONDITION_DELTA: dict[tuple[str, str], float] = {
    ("양호", "높음"): 1.5,
    ("양호", "낮음"): 1.0,
    ("주의", "높음"): -1.5,
    ("주의", "낮음"): -1.0,
    ("보통", "높음"): 0.0,
    ("보통", "낮음"): 0.0,
}

# cross_check.status → 점수 보정. note(보호자 노출용 문장)는 그대로 근거로 재사용.
_CROSS_CHECK_DELTA: dict[str, float] = {
    "mismatch_high_risk": -1.0,  # 센서 수면부족인데 본인은 괜찮다 — 숨은 위험
    "agree_low": -1.0,  # 수면·기분 둘 다 나쁨(일치)
    "mismatch": -0.5,  # 수면 좋은데 기분 나쁨
    "agree_ok": 0.0,
    "unknown": 0.0,
}

# 휴대폰 사용 concern_level(0~2) 당 보정 — phone_usage.py는 이미 advisory로
# 설계됐으므로 여기서도 작게만 반영(점수 좌우 X, 보조 신호).
_PHONE_CONCERN_STEP = -0.5

# 미션 완료율 보정 임계값.
_MISSION_HIGH = 0.7
_MISSION_LOW = 0.2
_MISSION_DELTA = 0.5


def _clamp_score(value: float) -> int:
    return max(_MIN_SCORE, min(_MAX_SCORE, round(value)))


def _level_for(score: int) -> str:
    """점수(1~10) → 등급 라벨(코드 정본). LLM은 이 등급을 뒤집지 않습니다."""
    if score >= 7:
        return prompt_mod.LEVEL_GOOD
    if score <= 3:
        return prompt_mod.LEVEL_WATCH
    return prompt_mod.LEVEL_NEUTRAL


def _condition_delta_and_evidence(
    condition: Optional[dict[str, Any]],
) -> tuple[float, Optional[str]]:
    if not condition:
        return 0.0, None
    cond = str(condition.get("condition") or "")
    conf = str(condition.get("confidence") or "")
    delta = _CONDITION_DELTA.get((cond, conf), 0.0)
    if not cond:
        return 0.0, None
    return delta, f"건강 데이터 기반 컨디션 추정: {cond}(신뢰도 {conf or '낮음'})"


def _cross_check_delta_and_evidence(
    cross_check: Optional[dict[str, Any]],
) -> tuple[float, Optional[str]]:
    if not cross_check:
        return 0.0, None
    status = str(cross_check.get("status") or "unknown")
    delta = _CROSS_CHECK_DELTA.get(status, 0.0)
    note = cross_check.get("note")
    if delta == 0.0 or not note:
        return delta, None
    return delta, str(note)


def _phone_usage_delta_and_evidence(
    phone_usage: Optional[dict[str, Any]],
) -> tuple[float, Optional[str]]:
    if not phone_usage:
        return 0.0, None
    concern = phone_usage.get("concern_level")
    try:
        concern = int(concern or 0)
    except (TypeError, ValueError):
        concern = 0
    if concern <= 0:
        return 0.0, None
    delta = _PHONE_CONCERN_STEP * concern
    reason = phone_usage.get("reason")
    return delta, str(reason) if reason else None


def _mission_delta_and_evidence(
    mission_completion_rate: Optional[float],
) -> tuple[float, Optional[str]]:
    if mission_completion_rate is None:
        return 0.0, None
    rate = float(mission_completion_rate)
    pct = round(rate * 100)
    if rate >= _MISSION_HIGH:
        return _MISSION_DELTA, f"최근 미션 완료율 {pct}% — 꾸준히 활동 중이에요."
    if rate <= _MISSION_LOW:
        return -_MISSION_DELTA, f"최근 미션 완료율 {pct}% — 활동이 줄었어요."
    return 0.0, f"최근 미션 완료율 {pct}%"


def _parse_llm_sentence(raw: str) -> str:
    try:
        data = json.loads(raw)
    except (TypeError, ValueError, json.JSONDecodeError):
        return ""
    if not isinstance(data, dict):
        return ""
    return str(data.get("sentence", "")).strip()


def _sentence_ok(sentence: str) -> bool:
    """LLM 문장 가드: 비어있지 않고 금칙어(진단·추측·위기암시) 없음."""
    if not sentence:
        return False
    return not any(bad in sentence for bad in prompt_mod.FORBIDDEN)


def infer_emotion(
    *,
    condition: Optional[dict[str, Any]] = None,
    cross_check: Optional[dict[str, Any]] = None,
    phone_usage: Optional[dict[str, Any]] = None,
    mission_completion_rate: Optional[float] = None,
    generate: Optional[GenerateFn] = None,
) -> dict[str, Any]:
    """background 신호로 오늘의 감정 체크인 점수(1~10)를 추론합니다.

    Args:
        condition: `recovery_signal.condition` — ``{"condition": "양호"|"주의"|
            "보통", "confidence": "높음"|"낮음"}`` 또는 ``None``(체크인<3 또는
            수면데이터 없음 — graceful, 기여 0).
        cross_check: `recovery_signal.cross_check` — 센서-자기인식 교차검증.
            ``note``(보호자 노출용 문장)가 있으면 근거로 그대로 재사용합니다.
        phone_usage: `phone_usage.analyze_phone_usage()` 결과(또는 ``None``).
            `concern_level`(0~2)만 봅니다 — advisory 신호라 가중치를 작게 둡니다.
        mission_completion_rate: 최근 미션 완료율(0~1) 또는 ``None``.
        generate: LLM 호출 함수(provider.generate). ``None`` 이면 규칙 문장만 사용.
            주입돼도 등급을 뒤집거나 금칙어가 섞이면 규칙 문장으로 폴백.

    Returns:
        ``{"emotion_score": int(1~10), "level": "좋음"|"보통"|"주의",
        "confidence": "높음"|"낮음", "evidence": [...], "source": "rule"|"llm"}``.

        - ``emotion_score`` 는 **항상 규칙으로 확정**(LLM이 바꾸지 않음) — 회복
          게이트·1인칭 편지 허용 여부에 쓰이는 안전 민감 값이라 결정론 유지.
        - ``confidence``: 입력 신호가 전혀 없으면(``condition`` 도 없음) "낮음".
        - ``evidence``: 코드가 만든 근거 문장 목록(정본) + (LLM 채택 시) 관찰
          문장 1개 추가.
    """
    score = _BASELINE
    evidence: list[str] = []
    have_signal = False

    delta, note = _condition_delta_and_evidence(condition)
    score += delta
    if note:
        evidence.append(note)
        have_signal = True

    delta, note = _cross_check_delta_and_evidence(cross_check)
    score += delta
    if note:
        evidence.append(note)
        have_signal = True

    delta, note = _phone_usage_delta_and_evidence(phone_usage)
    score += delta
    if note:
        evidence.append(note)
        have_signal = True

    delta, note = _mission_delta_and_evidence(mission_completion_rate)
    score += delta
    if note:
        evidence.append(note)
        have_signal = True

    emotion_score = _clamp_score(score)
    level = _level_for(emotion_score)
    confidence = "높음" if have_signal else "낮음"

    if not evidence:
        evidence.append("배경 정보가 부족해 중립값으로 추정했어요.")

    source = "rule"
    if generate is not None:
        try:
            raw = generate(
                prompt_mod.build_prompt(level, evidence),
                max_tokens=_MAX_TOKENS,
                temperature=_TEMPERATURE,
                json_mode=True,
            )
            sentence = _parse_llm_sentence(raw)
        except Exception:  # noqa: BLE001 — 추론 실패는 규칙 폴백으로 흡수(graceful)
            sentence = ""
        if _sentence_ok(sentence):
            evidence = [*evidence, sentence]
            source = "llm"

    return {
        "emotion_score": emotion_score,
        "level": level,
        "confidence": confidence,
        "evidence": evidence,
        "source": source,
    }
