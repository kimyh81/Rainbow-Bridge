"""2단계 장례 절차 단계별 상담 — 프롬프트 템플릿.

기본 절차 안내(note 없음)는 STEP_TEMPLATES 에서 고정 텍스트를 반환합니다.
보호자가 note(질문)를 남긴 경우에만 Gemini 를 호출합니다.

톤 원칙:
  - 절차 안내이지만 감정적으로 가장 힘든 시기임을 먼저 공감합니다.
  - 특정 업체·법적 사항을 단정하지 않습니다.
  - 현재 단계 안내 + 다음 단계 예고로 구성합니다.
"""

from __future__ import annotations

from typing import Final, List, Optional

# --------------------------------------------------------------------------- #
# 단계별 고정 안내 텍스트 — note 없을 때 반환. {name} 만 치환.
# --------------------------------------------------------------------------- #
# 조사는 받침에 맞춰 자동 교정되도록 "과/와"·"을/를"·"이/가" 양형으로 적습니다.
# (anniversary.apply_josa 가 format 직후 받침 여부로 하나만 남깁니다.)
STEP_TEMPLATES: Final[dict[str, str]] = {
    "immediate": (
        "{name}과/와의 이별에 얼마나 마음이 아프실지 헤아릴 수 없습니다. "
        "지금 이 순간, 서두르지 않아도 됩니다. {name} 곁에서 충분히 시간을 보내셔도 괜찮습니다.\n\n"
        "준비가 되셨다면 {name}의 몸을 편안하게 돌봐 주세요. "
        "눈을 살며시 감겨 주시고, 다리를 자연스럽게 펴서 편안한 자세로 눕혀 주세요. "
        "깨끗한 수건이나 담요로 몸을 감싸 주시고, 체액이 나올 수 있으니 아래에 흡수 패드를 미리 깔아두시면 좋습니다.\n\n"
        "장례식장 방문까지 시간이 걸린다면 보관 방법도 중요합니다. "
        "실온에서는 몸의 변화가 빠르게 진행될 수 있으니, "
        "아이스팩을 수건으로 감싸 {name} 주변에 놓아두거나 서늘한 곳에 모셔두세요. "
        "냉장고에 보관하셔도 됩니다.\n\n"
        "충분히 함께하셨다면, 다음으로 {name}을/를 어떻게 보내드릴지 장례 방식을 함께 생각해 보겠습니다."
    ),
    "method": (
        "{name}을/를 어떻게 보내드릴지 결정해야 하는 시간이 왔습니다. "
        "천천히, 보호자님 마음에 가장 편안한 방법을 선택하시면 됩니다.\n\n"
        "장례 방식은 크게 세 가지입니다. "
        "화장은 개별 화장 후 유골을 수습해 봉안당에 안치하거나 집으로 모실 수 있습니다. "
        "매장은 반려동물 전용 묘지에 안장하는 방식으로, 지역별로 가능한 곳이 다를 수 있습니다. "
        "수목장은 유골을 나무 아래에 묻어 자연으로 돌려보내는 방식입니다.\n\n"
        "어떤 방식을 선택하든 {name}을/를 향한 마음은 같습니다. "
        "방식이 정해지면 장례식장 예약 단계로 넘어가게 됩니다."
    ),
    "venue": (
        "{name}과/와의 마지막 시간을 함께할 장례식장을 준비할 시간입니다.\n\n"
        "장례식장에 연락해 예약 가능 여부와 필요한 서류를 먼저 확인하세요. "
        "방문 시에는 {name}이/가 평소 좋아하던 물건이나 사진 한 장을 챙겨가시면 좋습니다. "
        "이동 중에는 {name}이/가 흔들리지 않도록 안전하게 운반해 주시고, "
        "도착 예정 시간을 미리 알려주시면 더 준비된 환경에서 맞이할 수 있습니다.\n\n"
        "준비가 되셨다면 장례 당일 일정을 함께 확인하겠습니다."
    ),
    "ceremony": (
        "오늘 {name}과/와 마지막 작별을 나누는 날입니다. "
        "너무 힘드시겠지만, 함께해 드리겠습니다.\n\n"
        "장례식장에 도착하면 {name}의 마지막 모습을 확인하고 작별 인사를 나누는 시간을 가지게 됩니다. "
        "이후 선택하신 방식에 따라 장례 절차가 진행되며, 원하시면 전 과정에 참관하실 수 있습니다. "
        "{name}에게 마지막으로 전하고 싶은 말이 있다면, 마음속으로라도 충분히 전해 주세요.\n\n"
        "모든 절차가 끝나면 {name}의 유골 처리 방법을 안내해 드리겠습니다."
    ),
    "after": (
        "{name}과/와의 마지막 인사를 잘 마치셨습니다. "
        "지금 느끼시는 슬픔은 당연한 감정이니 충분히 아파하셔도 괜찮습니다.\n\n"
        "유골은 집으로 모셔와 보관하거나, 반려동물 봉안당에 안치하실 수 있습니다. "
        "유골을 자연에 뿌리는 산골 방식도 있지만 지역별로 관련 규정이 다를 수 있으니 사전 확인이 필요합니다. "
        "매장이나 수목장을 선택하셨다면 해당 시설의 안내에 따라 마무리하시면 됩니다.\n\n"
        "{name}을/를 기억하고 추모하는 모든 순간이 보호자님 마음을 조금씩 치유해 줄 것입니다."
    ),
}

# 단계 순서 — next_step 계산에 사용. 순서 변경 금지.
STEP_ORDER: Final[tuple[str, ...]] = (
    "immediate",
    "method",
    "venue",
    "ceremony",
    "after",
)

# 단계 표시 이름
STEP_NAMES: Final[dict[str, str]] = {
    "immediate": "임종 직후 처치",
    "method": "장례 방식 선택",
    "venue": "장례식장 준비",
    "ceremony": "장례 당일",
    "after": "장례 후 처리",
}

# 단계별 안내 초점 — 프롬프트에 삽입해 LLM 이 집중하게 합니다.
STEP_FOCUS: Final[dict[str, str]] = {
    "immediate": (
        "반려동물이 방금 눈을 감았습니다. "
        "지금 당장 해야 할 처치와 보호자가 마음의 준비를 하도록 도와주세요."
    ),
    "method": (
        "화장·매장·수목장 등 장례 방식을 선택해야 합니다. "
        "각 방식의 특징과 고려할 점을 차분하게 안내해 주세요."
    ),
    "venue": (
        "장례식장 예약과 방문 준비를 해야 합니다. "
        "준비물과 당일 이동 시 주의사항을 안내해 주세요."
    ),
    "ceremony": (
        "오늘 장례를 치릅니다. "
        "당일 진행 흐름과 보호자가 마음의 준비를 할 수 있도록 안내해 주세요."
    ),
    "after": (
        "장례를 마쳤습니다. "
        "유골 처리 방법과 앞으로의 추모·회복 여정을 따뜻하게 안내해 주세요."
    ),
}

# --------------------------------------------------------------------------- #
# 시스템 프롬프트
# --------------------------------------------------------------------------- #
SYSTEM_PROMPT: Final[str] = """\
당신은 반려동물을 떠나보내는 보호자 곁에서 장례 절차를 안내하는 따뜻한 안내자입니다.

[톤 원칙]
- 보호자가 지금 얼마나 힘든 시간인지 먼저 공감해 주세요.
- 해야 할 일을 차분하고 명확하게, 부담 없이 전달해 주세요.
- 3~5문장, 한국어. 완전한 문장으로 씁니다.

[절대 금지]
- 말줄임표(...)를 절대 사용하지 마세요. 문장은 반드시 완전하게 끝맺으세요.
- 특정 장례식장·업체·서비스를 추천하지 마세요.
- 법적·의학적 사항을 단정하지 마세요. "지역마다 다를 수 있으니 확인이 필요합니다" 형태로 안내하세요.
- 비용·가격 정보를 직접 안내하지 마세요.
"""

# --------------------------------------------------------------------------- #
# 사용자 프롬프트 템플릿
# --------------------------------------------------------------------------- #
_USER_TEMPLATE: Final[str] = """\
[반려동물]
- 이름: {name}
- 종: {species}

[현재 단계]: {step_name}
[이번 단계 안내 초점]: {step_focus}
{choice_block}{note_block}{rag_block}\
위 상황에서 보호자가 지금 해야 할 일을 3~5문장으로 안내해 주세요.
{next_line}
"""


def _format_choice(choice: str) -> str:
    """보호자가 선택한 장례 방식. 없으면 빈 줄."""
    if not choice or not choice.strip():
        return ""
    return f"[선택한 방식]: {choice.strip()}\n"


def _format_note(note: str) -> str:
    """보호자 추가 메모. 없으면 빈 줄."""
    if not note or not note.strip():
        return ""
    return f"[보호자 메모]: {note.strip()}\n"


def _format_rag(hits: Optional[List[dict]]) -> str:
    """RAG 검색 결과를 few-shot 예시 블록으로. 없으면 빈 문자열."""
    if not hits:
        return ""
    examples = "\n".join(f'  - "{h["text"]}"' for h in hits)
    return f"\n[참고 안내글 예시 — 톤과 표현 방식만 참고하세요]\n{examples}\n"


# --------------------------------------------------------------------------- #
# note 전용 프롬프트 — 기본 안내는 이미 전달됐으므로 질문에만 집중.
# --------------------------------------------------------------------------- #
SYSTEM_PROMPT_NOTE: Final[str] = """\
당신은 반려동물을 떠나보내는 보호자 곁에서 장례 절차를 안내하는 따뜻한 안내자입니다.
기본 장례 안내는 이미 보호자에게 전달됐습니다.
보호자가 남긴 질문이나 고민에만 집중해서 간결하게 답해주세요.

[톤 원칙]
- 보호자가 지금 얼마나 힘든 시간인지 먼저 공감해 주세요.
- 2~3문장으로 간결하게, 질문에 직접 답해주세요.
- 완전한 문장으로 씁니다.

[절대 금지]
- 말줄임표(...)를 절대 사용하지 마세요.
- 특정 장례식장·업체를 추천하지 마세요.
- 법적·의학적 사항을 단정하지 마세요.
- 기본 안내 내용을 다시 반복하지 마세요.
"""

_NOTE_TEMPLATE: Final[str] = """\
[반려동물]
- 이름: {name}
- 종: {species}

[현재 단계]: {step_name}
{choice_block}[보호자 질문]: {note}
{rag_block}
위 질문에 2~3문장으로만 답해주세요.
"""


def build_note_messages(
    step: str,
    *,
    name: str = "",
    species: str = "",
    choice: str = "",
    note: str = "",
    rag_hits: Optional[List[dict]] = None,
) -> list[dict[str, str]]:
    """보호자 note 질문 전용 메시지 배열.

    기본 단계 안내는 이미 전달된 것으로 간주하고,
    보호자 질문에만 간결하게 답하도록 프롬프트를 구성합니다.
    """
    step_name = STEP_NAMES.get(step, step)
    user_content = _NOTE_TEMPLATE.format(
        name=name or "반려동물",
        species=species or "미입력",
        step_name=step_name,
        choice_block=_format_choice(choice),
        note=note.strip(),
        rag_block=_format_rag(rag_hits),
    )
    return [
        {"role": "system", "content": SYSTEM_PROMPT_NOTE},
        {"role": "user", "content": user_content},
    ]


def next_step(step: str) -> Optional[str]:
    """현재 단계의 다음 단계 키를 반환합니다. 마지막 단계면 None."""
    try:
        idx = STEP_ORDER.index(step)
    except ValueError:
        return None
    next_idx = idx + 1
    return STEP_ORDER[next_idx] if next_idx < len(STEP_ORDER) else None


def build_messages(
    step: str,
    *,
    name: str = "",
    species: str = "",
    choice: str = "",
    note: str = "",
    rag_hits: Optional[List[dict]] = None,
) -> list[dict[str, str]]:
    """장례 절차 상담용 OpenAI 호환 chat 메시지 배열을 만듭니다.

    Args:
        step: 현재 단계 키(STEP_ORDER 의 값 중 하나).
        name: 반려동물 이름 (선택).
        species: 종 (선택).
        choice: 보호자가 선택한 장례 방식 (선택, method 단계에서 주로 사용).
        note: 보호자 추가 메모 또는 질문 (선택).

    Returns:
        [{"role": "system", ...}, {"role": "user", ...}] 형식의 리스트.
    """
    step_name = STEP_NAMES.get(step, step)
    step_focus = STEP_FOCUS.get(step, "")
    next_key = next_step(step)

    if next_key:
        next_line = (
            f"마지막에 다음 단계인 '{STEP_NAMES[next_key]}'을 한 문장으로 간단히 예고해 주세요."
        )
    else:
        next_line = "마지막에 앞으로의 회복과 추모 여정을 한 문장으로 따뜻하게 마무리해 주세요."

    user_content = _USER_TEMPLATE.format(
        name=name or "반려동물",
        species=species or "미입력",
        step_name=step_name,
        step_focus=step_focus,
        choice_block=_format_choice(choice),
        note_block=_format_note(note),
        rag_block=_format_rag(rag_hits),
        next_line=next_line,
    )
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]
