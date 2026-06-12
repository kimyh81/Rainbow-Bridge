"""2단계 장례 절차 단계별 상담 — 로직.

보호자가 현재 어느 장례 단계에 있는지 입력하면, 해당 단계 안내 텍스트를 생성합니다.
프롬프트(대본)는 prompts/funeral.py 에, 위기 판단은 safety.py 에 분리돼 있고,
이 파일은 그 둘을 엮어 흐름을 담당합니다:

    입력 → (1) 보호자 위기 선체크 → (2) 프롬프트 조립 → (3) LLM 호출 → 결과 dict

🚨 장례 준비 시기는 보호자 감정이 극도로 예민한 시기입니다.
보호자 메모(note)에 위기 신호가 있으면 절차 안내보다 1393 안내를 우선합니다.
"""

from __future__ import annotations

from typing import Optional, Protocol

from ai.rag.retrieve import retrieve as _rag_retrieve
from .prompts import funeral as funeral_prompt
from .prompts.anniversary import apply_josa
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
        temperature: float = 0.5,
        json_mode: bool = False,
    ) -> str: ...


# 절차 안내는 정확성이 중요해 temperature 를 낮게 설정.
_MAX_TOKENS: int = 350
_TEMPERATURE: float = 0.5

def generate_funeral_guidance(
    step: str,
    pet: dict,
    *,
    note: str = "",
    choice: str = "",
    generate: GenerateFn,
    source: str = "local",
) -> dict:
    """장례 절차 단계별 안내를 생성합니다.

    Args:
        step: 현재 장례 단계 키(funeral_prompt.STEP_ORDER 중 하나).
        pet: 반려동물 정보 ``{name, species}``.
        note: 보호자 감정 메모 또는 질문 (선택). 위기 선체크에도 사용.
        choice: 보호자가 선택한 장례 방식 (선택, method 단계에서 주로 사용).
        generate: LLM 호출 함수(provider.generate 또는 테스트용 가짜). **주입 필수.**
        source: 결과 출처 표기(local·perso 등).

    Returns:
        ``{guidance, step, next_step, source}``.
        보호자 위기 감지 시 ``crisis_message`` 와 ``risk_level`` 포함.
    """
    # (1) 보호자 메모 위기 선체크 — 등급별 응답 정책(safety.decide_action).
    #     L2(경고)·L3(긴급)이면 절차 안내보다 1393 우선.
    action = CrisisAction.GENERATE
    crisis = None
    if note:
        crisis = detect_crisis(note)
        action = decide_action(crisis.risk_level)
        if action == CrisisAction.BLOCK:  # L3 — 안내 중단, 1393 만
            notice = crisis_notice()
            return {
                "guidance": notice,
                "step": step,
                "next_step": None,
                "source": "safety",
                "crisis_message": notice,
                "risk_level": int(crisis.risk_level),
            }

    # (2) guidance 는 항상 STEP_TEMPLATES — note 유무와 무관하게 일관된 단계 안내.
    template = funeral_prompt.STEP_TEMPLATES.get(step, "")
    # 이름 받침에 맞춰 조사를 교정. 펫 이름은 친근형(받침 시 애칭 '이' — "콩이와의").
    guidance = apply_josa(template.format(name=pet.get("name", "반려동물")), friendly=True)

    # (3) note 없으면 템플릿만 반환 — Gemini 호출 없음.
    if not note:
        return {
            "guidance": guidance,
            "step": step,
            "next_step": funeral_prompt.next_step(step),
            "source": "template",
        }

    # (4) RAG 검색 — note 질문 관련 top-3 검색. 실패 시 graceful fallback.
    rag_hits = None
    try:
        query_parts: list[str] = [note]
        step_focus = funeral_prompt.STEP_FOCUS.get(step, "")
        if step_focus:
            query_parts.append(step_focus)
        rag_hits = _rag_retrieve(" ".join(query_parts), k=3, where={"category": "funeral"})
    except Exception:
        rag_hits = None

    # (5) note 있으면 Gemini — 질문에만 답변 (단계 안내는 guidance 에 이미 있음).
    messages = funeral_prompt.build_note_messages(
        step,
        name=pet.get("name", ""),
        species=pet.get("species", ""),
        choice=choice,
        note=note,
        rag_hits=rag_hits,
    )
    prompt = f"{messages[0]['content']}\n\n{messages[1]['content']}"
    # L1(우려)·L2(경고) — 절차 정보보다 공감을 먼저 하도록 지침 추가.
    if action in (CrisisAction.GENERATE_WITH_SUPPORT, CrisisAction.HOTLINE):
        prompt += EMPATHY_FOCUS_NOTE
    # LLM 인프라 실패 시: 단계 안내(guidance, 템플릿)는 유지하고 개인화 답변만
    # 안내문으로 graceful 대체(source=unavailable). 앱이 터지지 않게.
    try:
        note_response = generate(
            prompt, max_tokens=_MAX_TOKENS, temperature=_TEMPERATURE
        ).strip()
    except LLMError:
        note_response = LLM_UNAVAILABLE_NOTICE
        source = "unavailable"

    result = {
        "guidance": guidance,
        "note_response": note_response,
        "step": step,
        "next_step": funeral_prompt.next_step(step),
        "source": source,
    }
    # L1(우려) — 절차 안내는 하되 복지자원 안내를 함께.
    if action == CrisisAction.GENERATE_WITH_SUPPORT and crisis is not None:
        result["support_message"] = WELFARE_INTRO
        result["welfare_resources"] = list(WELFARE_RESOURCES)
        result["risk_level"] = int(crisis.risk_level)
    # L2(경고) — 절차 안내는 하되 1393 안내를 함께(우선 표시).
    elif action == CrisisAction.HOTLINE and crisis is not None:
        result["crisis_message"] = crisis_notice()
        result["risk_level"] = int(crisis.risk_level)
    return result
