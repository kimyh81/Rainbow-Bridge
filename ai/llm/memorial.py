"""③ 추모 메시지 생성 — 로직.

보호자가 들려준 기억을 바탕으로 **보호자를 위로하는** 추모 메시지를 만듭니다.
프롬프트(대본)는 prompts/memorial.py 에, 위기 판단은 safety.py 에 분리돼 있고,
이 파일은 그 둘을 엮어 **흐름**을 담당합니다:

    입력 → (1) 위기 선체크 → (2) 프롬프트 조립 → (3) LLM 호출
         → (4) 후처리 가드(부활 차단 / 1인칭 모드가 아니면 1인칭도 차단) → 결과 dict

🚫 윤리 경계 (../CLAUDE.md §0):
  - 반려동물 부활은 모든 모드에서 금지 → 출력에서도 후처리로 한 번 더 거릅니다.
  - 1인칭 화법은 first_person=True(§1.5 조건 충족) 일 때만 허용.
    호출자가 보호자 동의·경고 문구 표시·risk_level 0~1 을 보장해야 합니다.
  - 위기 신호가 강하면(L2↑) 메시지 생성보다 1393 안내가 **우선**입니다.

LLM 호출(provider.generate)은 **주입(generate 인자)** 받습니다. 덕분에 엔진이
확정되기 전에도 가짜 generate 로 흐름·가드를 테스트할 수 있고, 확정 후에는
provider.generate 를 그대로 넘기면 됩니다(결정 A/B).
"""

from __future__ import annotations

import re
from typing import Optional, Protocol

from ai.rag.retrieve import retrieve as _rag_retrieve
from .prompts import memorial as memorial_prompt
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
        max_tokens: int = 400,
        temperature: float = 0.7,
        json_mode: bool = False,
    ) -> str: ...


# 생성 파라미터 기본값 (config 확정 전 잠정값).
# 추모 글 목표 길이 600자 안팎(2026-06-09 2배 상향)에 맞춰 토큰 한도도 상향.
_MAX_TOKENS: int = 800
_TEMPERATURE: float = 0.7

class GuardrailViolation(Exception):
    """생성 결과가 윤리 경계(1인칭/부활)를 넘었을 때."""


# --------------------------------------------------------------------------- #
# 후처리 가드 — LLM이 경계를 넘으면 잡아냅니다(2차 안전망).
# --------------------------------------------------------------------------- #
# 부활/환생 등 "돌아온다"는 단정 표현.
_RESURRECTION_MARKERS: tuple[str, ...] = (
    "다시살아",
    "다시태어",
    "되살아",
    "부활",
    "환생",
    "돌아올거",
    "돌아온다",
    "다시만날수있어",
)


# 반려동물 1인칭 표현 — 보호자 시점("나는 봄이가 그리워요")과 구분하기 위해
# 반려동물 이름과 같은 문장에 등장할 때만 차단합니다.
_FIRST_PERSON_MARKERS: tuple[str, ...] = (
    "나는", "저는", "내가", "제가", "나예요", "저예요", "나야", "나랍니다",
)

# 1인칭 마커는 '단어 시작'에서만 인정한다(부분일치 오탐 방지).
#   "빛나는·만나는·일어나는"의 '나는', "문제가"의 '제가' 등을 1인칭으로 오인하지
#   않도록, 앞이 문장 시작이거나 공백/문장부호일 때만 매칭한다.
_FIRST_PERSON_RE: re.Pattern = re.compile(
    r"(?:^|(?<=[\s,.!?\"'()\[\]{}·…~\-]))(?:" + "|".join(_FIRST_PERSON_MARKERS) + r")"
)

_SENTENCE_SPLIT: re.Pattern = re.compile(r"[.!?。\n]")


def _has_pet_first_person(content: str, pet_name: str) -> bool:
    """반려동물 이름과 1인칭 표현이 같은 문장에 있으면 반려동물 화법으로 판단."""
    if not pet_name:
        return False
    for sentence in _SENTENCE_SPLIT.split(content):
        if pet_name in sentence and _FIRST_PERSON_RE.search(sentence):
            return True
    return False


def _violates_guardrail(
    content: str, pet_name: str = "", first_person: bool = False
) -> Optional[str]:
    """경계 위반 사유를 반환(없으면 None).

    - 부활/환생 단정 표현 — first_person 여부와 관계없이 항상 차단.
    - 반려동물 이름 + 1인칭이 같은 문장에 등장 — first_person=True 이면 허용.
      → 보호자가 "나는 봄이가 그리워요"라고 하는 경우는 차단하지 않습니다.
    - first_person=True 인데 반려동물이 1인칭으로 말하지 않음(LLM이 지시를
      무시하고 3인칭 내레이션을 반환) — "꿈 속 작별 편지" 라며 3인칭 글이
      그대로 나가는 것을 막기 위해 위반으로 처리하고 재생성을 유도합니다.
    """
    normalized = content.replace(" ", "")

    for marker in _RESURRECTION_MARKERS:
        if marker in normalized:
            return f"부활/환생 표현 감지: '{marker}'"

    if first_person:
        # 1인칭 모드: 펫이 나는/내가 등을 사용하면 통과.
        # 펫은 자신의 이름과 "나는"을 같은 문장에 쓰지 않는 게 자연스러우므로
        # 이름 동시 등장 조건 없이 1인칭 표현 존재 여부만 확인한다.
        if not _FIRST_PERSON_RE.search(content):
            return f"1인칭 모드 요청이지만 1인칭 화법(나는/내가 등) 미사용"
    elif _has_pet_first_person(content, pet_name):
        return f"반려동물({pet_name}) 1인칭 화법 감지"

    return None


def generate_message(
    pet: dict,
    emotion: dict,
    tone: str = memorial_prompt.DEFAULT_TONE,
    *,
    generate: GenerateFn,
    source: str = "local",
    max_retries: int = 1,
    first_person: bool = False,
    recovery_trend: Optional[str] = None,
    guardian_nickname: str = "",
) -> dict:
    """추모 메시지를 생성합니다.

    Args:
        pet: 반려동물 정보 ``{name, species, period, memories?, bucket_list?, caller_name?}``
            (백엔드 pet 스키마). ``bucket_list`` 는 함께 하고 싶었던 일(버킷리스트),
            ``caller_name`` 은 보호자 호칭(엄마·아빠·언니). 둘 다 선택 — 없으면 생략/기본값.
            백엔드가 ``pet_id`` 로 조회한 버킷리스트·타임라인을 이 키에 담아 넘깁니다.
        emotion: 보호자 감정 ``{emotion_score, note?}`` (emotion_score 1~10, 낮을수록 힘듦).
        tone: 메시지 톤(warm·calm·hopeful). prompts.TONE_GUIDE 키.
        generate: LLM 호출 함수(provider.generate 또는 테스트용 가짜). **주입 필수.**
        source: 결과 출처 표기(local·perso 등).
        max_retries: 가드 위반 시 재생성 횟수(소진되면 안내문으로 대체).
        first_person: True 이면 반려동물 1인칭 편지 모드(꿈 속 작별 대화).
            호출자가 보호자 동의·경고 문구 표시·risk_level 0~1 을 보장해야 합니다.
        recovery_trend: 최근 7회 추이(백엔드 get_recovery 의 trend: "회복 중"·"유지 중"
            ·"주의 필요"·"데이터 없음"). 톤을 덮어쓰지 않고 같은 톤 안에서 결을 맞추도록
            프롬프트에 신호로만 넣습니다. 없으면 생략(graceful).
            🚨 위기 선체크(아래)를 통과한 뒤에만 쓰여 위기 안내(1393) 우선순위를 깨지 않습니다.
        guardian_nickname: 보호자 회원가입 별명(user.nickname, 백엔드가 전달). **3인칭에서만**
            글 첫머리 "○○님," 호명에 사용. 1인칭 모드에선 무시. 없으면 호명 생략(graceful).
            pet 딕셔너리에 ``guardian_nickname`` 으로 담아 넘겨도 됩니다.

    Returns:
        ``{content, tone, source}``. 위기 시에는 ``crisis_message`` 와 ``risk_level`` 포함.
        1인칭 모드이면 ``first_person: True`` 가 함께 반환됩니다.
    """
    note = str(emotion.get("note", "") or "")

    # (1) 위기 선체크 — 등급별 응답 정책(safety.decide_action).
    #     L3(긴급)이면 생성 전면 중단, 1393 안내만. (L2 는 생성도 함께 — 아래 참고)
    crisis = detect_crisis(note)
    action = decide_action(crisis.risk_level)
    if action == CrisisAction.BLOCK:
        notice = crisis_notice()
        return {
            "content": notice,
            "tone": tone,
            "source": "safety",
            "crisis_message": notice,
            "risk_level": int(crisis.risk_level),
        }

    # 🚨 1인칭 펫 편지는 risk_level<=1 에서만. L2(경고)면 생성은 하되 강제로 3인칭으로
    #    낮춥니다 — 위기 신호가 있는 보호자에게 반려동물 1인칭 편지는 금지(안전 최우선).
    if action == CrisisAction.HOTLINE:
        first_person = False

    # (2) RAG 검색 — note + 추억 + 버킷리스트 키워드로 관련 위로글 top-3 검색.
    #     실패(DB 미적재·네트워크 오류 등) 시 graceful fallback.
    bucket_list = pet.get("bucket_list")
    rag_hits = None
    try:
        query_parts: list[str] = []
        if note:
            query_parts.append(note)
        for m in (pet.get("memories") or [])[:3]:
            if isinstance(m, dict):
                parts = [m.get("keyword", ""), m.get("detail", "")]
                query_parts.append(" ".join(p for p in parts if p))
            elif m:
                query_parts.append(str(m))
        for b in (bucket_list or [])[:3]:
            if isinstance(b, dict):
                parts = [b.get("keyword", "") or b.get("title", ""), b.get("detail", "")]
                query_parts.append(" ".join(p for p in parts if p))
            elif b:
                query_parts.append(str(b))
        if query_parts:
            rag_hits = _rag_retrieve(" ".join(query_parts), k=3, where={"category": "memorial"})
    except Exception:
        rag_hits = None

    # (3) 프롬프트 조립 — 키 이름은 백엔드 스키마와 합의(pet.period, emotion_score).
    #     버킷리스트·보호자 호칭은 pet 에서 꺼내 그대로 프롬프트로 전달(프롬프트는 동결).
    prompt_kwargs = dict(
        name=pet.get("name", ""),
        species=pet.get("species", ""),
        period=pet.get("period", ""),
        caller_name=str(pet.get("caller_name") or ""),
        guardian_nickname=str(guardian_nickname or pet.get("guardian_nickname", "")),
        score=int(emotion.get("emotion_score", 5)),
        note=note,
        memories=pet.get("memories"),
        bucket_list=bucket_list,
        tone=tone,
        first_person=first_person,
        rag_hits=rag_hits,
        recovery_trend=recovery_trend,
    )
    messages = memorial_prompt.build_messages(**prompt_kwargs)
    prompt = f"{messages[0]['content']}\n\n{messages[1]['content']}"
    # L1(우려)·L2(경고)는 공감 우선. 추가로 자책감이 감지되면(등급 무관) 공감 톤만
    # 얹는다 — 복지자원·1393 은 붙이지 않음(자책감은 펫로스 애도에 흔해 과민 안내 방지).
    if action in (CrisisAction.GENERATE_WITH_SUPPORT, CrisisAction.HOTLINE) or crisis.guilt:
        prompt += EMPATHY_FOCUS_NOTE

    # (4)+(5) 호출 후 가드 검사, 위반 시 재생성.
    #   LLM 인프라 실패(LLMError: 전 키·모델 소진 등)는 앱이 터지지 않게
    #   '명백한 안내문'으로 graceful 대체(source=unavailable). 가짜 추모글 금지.
    last_violation = ""
    try:
        attempts = range(max_retries + 1)
        for _ in attempts:
            content = generate(
                prompt, max_tokens=_MAX_TOKENS, temperature=_TEMPERATURE
            ).strip()
            violation = _violates_guardrail(
                content, pet_name=pet.get("name", ""), first_person=first_person
            )
            if violation is not None:
                last_violation = violation
                continue

            result = {"content": content, "tone": tone, "source": source}
            # L1(우려) — 생성은 하되 복지자원 안내를 함께.
            if action == CrisisAction.GENERATE_WITH_SUPPORT:
                result["support_message"] = WELFARE_INTRO
                result["welfare_resources"] = list(WELFARE_RESOURCES)
                result["risk_level"] = int(crisis.risk_level)
            # L2(경고) — 생성은 하되 1393 안내를 함께(우선 표시).
            elif action == CrisisAction.HOTLINE:
                result["crisis_message"] = crisis_notice()
                result["risk_level"] = int(crisis.risk_level)
            if first_person:
                result["first_person"] = True
            return result
    except LLMError:
        # 전 키·모델 소진 등 인프라 실패 → 안내문으로 graceful 대체(앱 안 터지게).
        return {
            "content": LLM_UNAVAILABLE_NOTICE,
            "tone": tone,
            "source": "unavailable",
        }

    # 재시도까지 가드 위반 → 위험한 출력을 내보내지 않고 차단.
    raise GuardrailViolation(
        f"생성 결과가 윤리 경계를 반복해서 위반했습니다 ({last_violation})."
    )
