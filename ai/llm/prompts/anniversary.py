"""3단계 기념일 케어 알림 — 프롬프트 템플릿.

무지개다리 D+30·D+100 시점에 보호자에게 발송하는 케어 메시지를 생성합니다.
기본 안내 문구(note 없음)는 MILESTONE_TEMPLATES 에서 고정 텍스트를 반환합니다.
보호자가 note(감정 메모)를 남긴 경우에만 Gemini 를 호출합니다.

톤 원칙:
  - 슬픔을 억지로 끝내지 않도록 — "이제 괜찮아야 해"가 아니라 "함께 걸어가겠습니다".
  - 일상 복귀는 {name}를 잊는 게 아님을 자연스럽게 담습니다.
  - D+30: 한 달의 무게를 인정, 조금씩 일상으로 나아가도록 격려.
  - D+100: 100일간 버텨온 보호자를 위로, {name}의 기억이 함께함을 전달.
"""

from __future__ import annotations

import re
from typing import Final, Optional

# 트리거 기념일 목록 — 추후 D+365 등 추가 시 여기에만 넣으면 됩니다.
MILESTONE_DAYS: Final[tuple[int, ...]] = (30, 100)


# --------------------------------------------------------------------------- #
# 조사 자동 교정 — 템플릿에 "{name}이/가"처럼 적고, 앞 글자 받침에 맞춰 하나로 고정.
# (받침 있는 이름 "푸딩" → "푸딩이/을/과", 없는 이름 "코코" → "코코가/를/와")
# --------------------------------------------------------------------------- #
_JOSA_RE = re.compile(r"(.)(이/가|을/를|과/와|은/는)")


def _has_jongseong(text: str) -> bool:
    """문자열 끝 글자에 받침이 있으면 True (한글이 아니면 False)."""
    if not text:
        return False
    code = ord(text[-1])
    if 0xAC00 <= code <= 0xD7A3:
        return (code - 0xAC00) % 28 != 0
    return False


def apply_josa(text: str, *, friendly: bool = False) -> str:
    """본문 속 '앞글자+이/가' 형태의 조사를 받침 여부에 맞게 교정합니다.

    - friendly=True: 받침 있는 이름에 애칭 '이'를 붙여 다정한 호칭으로 만듭니다
      (푸딩 → 푸딩이가/푸딩이를/푸딩이와). 추모·기념일 메시지용.
    - friendly=False(기본): 표준 조사만 고릅니다(푸딩 → 푸딩이/푸딩을/푸딩과).
      장례 안내처럼 격식이 필요한 곳에서 사용합니다.
    """

    def _repl(m: "re.Match[str]") -> str:
        prev, pair = m.group(1), m.group(2)
        jong, no_jong = pair.split("/")
        if _has_jongseong(prev):
            return prev + ("이" + no_jong if friendly else jong)
        return prev + no_jong

    return _JOSA_RE.sub(_repl, text)

# --------------------------------------------------------------------------- #
# 단계별 고정 안내 텍스트 — note 없을 때 반환. {name} 만 치환.
# --------------------------------------------------------------------------- #
MILESTONE_TEMPLATES: Final[dict[int, str]] = {
    30: (
        "{name}이/가 무지개다리를 건넌 지 한 달이 지났습니다. "
        "지난 한 달이 얼마나 힘드셨을지, 그 무게를 잘 알고 있습니다.\n\n"
        "조금씩 일상으로 돌아가는 것은 {name}을/를 잊는 게 아닙니다. "
        "{name}이/가 보호자님의 일상 속에서도 늘 함께하기를 바랐을 테니까요. "
        "밥을 챙겨 먹고, 바깥 공기를 마시는 작은 일들이 {name}을/를 향한 사랑의 연장입니다.\n\n"
        "오늘도 충분히 잘 하고 계십니다. 천천히 걸어가셔도 됩니다."
    ),
    100: (
        "{name}이/가 무지개다리를 건넌 지 100일이 지났습니다. "
        "100일 동안 버텨오신 보호자님께 진심으로 경의를 표합니다.\n\n"
        "{name}과/와 함께한 모든 순간은 사라지지 않습니다. "
        "함께 나눈 온기, 함께한 아침과 저녁, 그 기억들이 보호자님의 마음속에서 "
        "지금도 살아 숨 쉬고 있습니다.\n\n"
        "앞으로도 {name}을/를 그리워하는 날이 오겠지만, "
        "그 그리움이 조금씩 따뜻한 추억으로 변해갈 거라 믿습니다. "
        "보호자님의 회복 여정을 언제나 응원합니다."
    ),
}

# 기념일 이름 표시
MILESTONE_LABELS: Final[dict[int, str]] = {
    30: "한 달",
    100: "100일",
}

# 단계별 안내 초점 — Gemini 호출 시 프롬프트에 삽입.
MILESTONE_FOCUS: Final[dict[int, str]] = {
    30: (
        "{name}이/가 떠난 지 한 달이 지났습니다. "
        "일상 복귀가 {name}을/를 잊는 게 아님을 따뜻하게, "
        "억지로 괜찮아지라고 강요하지 않는 톤으로 안내해 주세요."
    ),
    100: (
        "{name}이/가 떠난 지 100일이 지났습니다. "
        "100일 동안 버텨온 보호자님을 위로하고, "
        "{name}의 기억이 보호자님 곁에 영원히 남아있음을 희망적으로 전해 주세요."
    ),
}

# --------------------------------------------------------------------------- #
# 시스템 프롬프트
# --------------------------------------------------------------------------- #
SYSTEM_PROMPT: Final[str] = """\
당신은 반려동물을 잃은 보호자의 회복을 돕는 따뜻한 동반자입니다.
기념일 메시지를 통해 보호자가 혼자가 아님을 느끼게 해주세요.

[톤 원칙]
- "이제 괜찮아야 해"처럼 슬픔을 끝내도록 강요하지 마세요.
- 일상 복귀는 반려동물을 잊는 것이 아님을 자연스럽게 담아 주세요.
- 3~5문장, 한국어, 완전한 문장으로 씁니다.

[절대 금지]
- 말줄임표(...)를 절대 사용하지 마세요. 문장은 반드시 완전하게 끝맺으세요.
- 반려동물이 말하는 것처럼 쓰지 마세요. 보호자를 위로하는 관점으로만 씁니다.
- "곧 나아질 거예요" 같은 근거 없는 확언을 하지 마세요.
"""

# --------------------------------------------------------------------------- #
# 사용자 프롬프트 템플릿
# --------------------------------------------------------------------------- #
_USER_TEMPLATE: Final[str] = """\
[반려동물]
- 이름: {name}
- 종: {species}
{memories_block}
[기념일]: {milestone_label}({days_since}일)
[안내 초점]: {milestone_focus}
{note_block}\
위 상황에서 보호자님께 3~5문장의 기념일 케어 메시지를 작성해 주세요.
"""


def _format_memories(memories: Optional[list[str]]) -> str:
    if not memories:
        return ""
    joined = ", ".join(str(m) for m in memories if m)
    return f"- 기억: {joined}\n" if joined else ""


def _format_note(note: str) -> str:
    if not note or not note.strip():
        return ""
    return f"[보호자 메모]: {note.strip()}\n"


def build_messages(
    days_since: int,
    *,
    name: str = "",
    species: str = "",
    memories: Optional[list[str]] = None,
    note: str = "",
) -> list[dict[str, str]]:
    """기념일 케어 메시지용 OpenAI 호환 chat 메시지 배열을 만듭니다.

    Args:
        days_since: 무지개다리 이후 일수(30 또는 100).
        name: 반려동물 이름.
        species: 종.
        memories: 보호자가 입력한 기억 조각 목록.
        note: 보호자 감정 메모 또는 질문.

    Returns:
        [{"role": "system", ...}, {"role": "user", ...}] 형식의 리스트.
    """
    milestone_label = MILESTONE_LABELS.get(days_since, f"{days_since}일")
    raw_focus = MILESTONE_FOCUS.get(days_since, "")
    milestone_focus = (
        apply_josa(raw_focus.format(name=name or "반려동물"), friendly=True)
        if raw_focus
        else ""
    )

    user_content = _USER_TEMPLATE.format(
        name=name or "반려동물",
        species=species or "미입력",
        memories_block=_format_memories(memories),
        milestone_label=milestone_label,
        days_since=days_since,
        milestone_focus=milestone_focus,
        note_block=_format_note(note),
    )
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]
