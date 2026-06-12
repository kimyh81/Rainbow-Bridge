"""3단계 기념일 케어 알림 — 로직.

무지개다리 D+30·D+100 시점을 감지하고, 보호자를 위한 케어 메시지를 생성합니다.
프롬프트(대본)는 prompts/anniversary.py 에, 위기 판단은 safety.py 에 분리돼 있고,
이 파일은 그 둘을 엮어 흐름을 담당합니다:

    날짜 입력 → check_anniversary 로 트리거 여부 확인
    → (1) 보호자 위기 선체크 → (2) note 없으면 템플릿 반환
    → (3) note 있으면 Gemini 호출 → 결과 dict

🚨 보호자가 감정 메모를 남긴 경우 위기 신호를 먼저 확인합니다.
위기 감지(L2↑) 시 케어 메시지보다 1393 안내가 우선입니다.
"""

from __future__ import annotations

from datetime import date
from typing import Optional, Protocol

from .prompts import anniversary as anniversary_prompt
from .provider import LLM_UNAVAILABLE_NOTICE, LLMError
from .safety import (
    CrisisAction,
    EMPATHY_FOCUS_NOTE,
    WELFARE_INTRO,
    WELFARE_RESOURCES,
    crisis_notice,
    decide_action,
    detect_crisis,
)


class GenerateFn(Protocol):
    """provider.generate 와 맞춘 호출 시그니처 (주입용)."""

    def __call__(
        self,
        prompt: str,
        *,
        max_tokens: int = 350,
        temperature: float = 0.6,
        json_mode: bool = False,
    ) -> str: ...


_MAX_TOKENS: int = 350
_TEMPERATURE: float = 0.6  # 위로 메시지 — memorial 보다 약간 낮게(정확성↑)

def check_anniversary(passed_date: date, today: date) -> Optional[int]:
    """오늘이 무지개다리 D+30 또는 D+100인지 확인합니다.

    Args:
        passed_date: 반려동물이 무지개다리를 건넌 날짜.
        today: 확인할 날짜(보통 오늘).

    Returns:
        트리거 일수(30 또는 100). 해당 없으면 None.
    """
    delta = (today - passed_date).days
    if delta in anniversary_prompt.MILESTONE_DAYS:
        return delta
    return None


def generate_anniversary_care(
    pet: dict,
    days_since: int,
    *,
    note: str = "",
    generate: GenerateFn,
    source: str = "local",
) -> dict:
    """기념일 케어 메시지를 생성합니다.

    Args:
        pet: 반려동물 정보 ``{name, species, memories?}``.
        days_since: 무지개다리 이후 일수(check_anniversary 반환값 또는 30·100).
        note: 보호자 감정 메모 (선택). 위기 선체크에도 사용.
        generate: LLM 호출 함수(provider.generate 또는 테스트용 가짜). **주입 필수.**
        source: 결과 출처 표기(local·perso 등).

    Returns:
        ``{message, days_since, milestone_label, source}``.
        위기 감지 시 ``crisis_message`` 와 ``risk_level`` 포함.
    """
    milestone_label = anniversary_prompt.MILESTONE_LABELS.get(
        days_since, f"{days_since}일"
    )

    # (1) 보호자 메모 위기 선체크 — 등급별 응답 정책(safety.decide_action).
    #     L2(경고)·L3(긴급)이면 케어 메시지보다 1393 우선.
    action = CrisisAction.GENERATE
    crisis = None
    if note:
        crisis = detect_crisis(note)
        action = decide_action(crisis.risk_level)
        if action == CrisisAction.BLOCK:  # L3 — 메시지 중단, 1393 만
            notice = crisis_notice()
            return {
                "message": notice,
                "days_since": days_since,
                "milestone_label": milestone_label,
                "source": "safety",
                "crisis_message": notice,
                "risk_level": int(crisis.risk_level),
            }

    # (2) note 없으면 고정 템플릿 반환 — Gemini 호출 없음.
    if not note:
        template = anniversary_prompt.MILESTONE_TEMPLATES.get(days_since, "")
        message = anniversary_prompt.apply_josa(
            template.format(name=pet.get("name") or "반려동물"), friendly=True
        )
        return {
            "message": message,
            "days_since": days_since,
            "milestone_label": milestone_label,
            "source": "template",
        }

    # (3) note 있으면 Gemini 호출 (보호자 감정에 맞춤 응답).
    messages = anniversary_prompt.build_messages(
        days_since,
        name=pet.get("name", ""),
        species=pet.get("species", ""),
        memories=pet.get("memories"),
        note=note,
    )
    prompt = f"{messages[0]['content']}\n\n{messages[1]['content']}"
    # L1(우려)·L2(경고) — 케어 메시지에서 공감을 먼저 하도록 지침 추가.
    if action in (CrisisAction.GENERATE_WITH_SUPPORT, CrisisAction.HOTLINE):
        prompt += EMPATHY_FOCUS_NOTE
    # LLM 인프라 실패 시: 안내문으로 graceful 대체(source=unavailable). 앱 안 터지게.
    try:
        message = generate(
            prompt, max_tokens=_MAX_TOKENS, temperature=_TEMPERATURE
        ).strip()
    except LLMError:
        message = LLM_UNAVAILABLE_NOTICE
        source = "unavailable"

    result = {
        "message": message,
        "days_since": days_since,
        "milestone_label": milestone_label,
        "source": source,
    }
    # L1(우려) — 케어 메시지는 하되 복지자원 안내를 함께.
    if action == CrisisAction.GENERATE_WITH_SUPPORT and crisis is not None:
        result["support_message"] = WELFARE_INTRO
        result["welfare_resources"] = list(WELFARE_RESOURCES)
        result["risk_level"] = int(crisis.risk_level)
    # L2(경고) — 케어 메시지는 하되 1393 안내를 함께(우선 표시).
    elif action == CrisisAction.HOTLINE and crisis is not None:
        result["crisis_message"] = crisis_notice()
        result["risk_level"] = int(crisis.risk_level)
    return result
