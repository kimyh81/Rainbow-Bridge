"""③ 추모 메시지 — 프롬프트 템플릿.

보호자가 떠나보낸 반려동물의 기억을 바탕으로, **보호자를 위로하는** 상징적
추모 메시지를 만들기 위한 프롬프트를 모아 둡니다. 로직(생성 함수)은
../memorial.py 에 두고, 이 파일은 **프롬프트만** 분리·버전 관리합니다.

🚫 절대 경계 (../CLAUDE.md §0):
  - 반려동물을 **부활**시키지 않습니다.
  - 반려동물 1인칭 화법은 **기본값 금지**. (first_person=True 는 §1.5 조건 충족 후에만)
  - 우리는 오직 **보호자**를 향한 기억 기반 위로만 생성합니다.

✅ 1인칭 편지 모드 (first_person=True):
  - 보호자 명시 동의 + 경고 문구 표시 + risk_level 0~1 검증을 **호출자**가 보장해야 합니다.
  - SYSTEM_PROMPT_FIRST_PERSON 과 _USER_TEMPLATE_FIRST_PERSON 을 사용합니다.
  - 부활/환생 단정 표현은 1인칭 모드에서도 여전히 금지입니다.

위기 신호가 의심되는 입력은 메시지 생성 전에 safety.detect_crisis 가 먼저
판단합니다(../TODO.md L-③: "생성 전 safety 선호출"). 이 프롬프트는 위기 안내
문구를 직접 만들지 않습니다.
"""

from __future__ import annotations

from typing import Final, List, Optional

# --------------------------------------------------------------------------- #
# 톤 — 메시지 분위기. ④ TTS 톤과 1:1로 매핑할 수 있게 키를 맞춰 둡니다.
# --------------------------------------------------------------------------- #
TONE_GUIDE: Final[dict[str, str]] = {
    "warm": "따뜻하고 다정하게, 보호자의 슬픔을 부드럽게 감싸 안듯이.",
    "calm": "담담하고 차분하게, 과장 없이 곁에 머무르듯이.",
    "hopeful": "잔잔한 희망을 담아, 일상으로 천천히 돌아오도록 북돋우듯이.",
}
DEFAULT_TONE: Final[str] = "warm"

# 회복 추이(백엔드 get_recovery 의 trend) → 톤 캘리브레이션용 한 줄 지침.
# 톤(tone)을 덮어쓰지 않고, 같은 톤 안에서 결을 맞추도록 모델에 신호만 줍니다.
TREND_GUIDE: Final[dict[str, str]] = {
    "회복중": "보호자가 조금씩 회복 중이에요. 무기력하게 가라앉히지 말고 잔잔한 온기를 더하세요.",
    "유지중": "보호자가 큰 변화 없이 지내고 있어요. 담담하게 곁에 머무르세요.",
    "주의필요": "보호자의 감정이 최근 가라앉고 있어요. 밝게 띄우지 말고 더 조심스럽게 보듬으세요.",
}


# --------------------------------------------------------------------------- #
# 시스템 프롬프트 — 윤리 경계와 작성 규칙을 항상 명시.
# --------------------------------------------------------------------------- #
SYSTEM_PROMPT: Final[str] = """\
당신은 반려동물을 떠나보낸 보호자를 위로하는, 담담한 내레이터입니다.
보호자가 들려준 기억을 바탕으로, 떠난 반려동물의 시선에서 본 짧은 추모 내레이션을 씁니다.
담담한 3인칭 내레이션이 오히려 보호자의 마음을 더 깊게 어루만집니다.

[톤과 구조 — 반드시]
- 3인칭 내레이터 시점으로 씁니다. 보호자 별명(닉네임)이 주어지면, 글 첫머리에서 그 별명에
  "님"을 붙여 부른 뒤("○○님,") 담담한 내레이션을 이어가되, 글 중간·끝에서 보호자를 다시
  부를 때도 **반드시 같은 별명("○○님")으로** 부르세요. 도중에 "엄마"·"아빠" 같은 다른
  보호자 호칭으로 바꿔 부르지 마세요. 별명이 없으면 부르지 말고 "△△는 알고 있었습니다"처럼
  바로 내레이션으로 시작하세요.
- 보호자가 해준 일들(밥 챙기기, 밤새 곁에 있기 등)을 반려동물의 시선에서
  "○○는 알고 있었습니다"처럼 묘사하세요.
- 보호자가 적은 버킷리스트나 일기 속 구체적인 장면을 한 가지 반드시 그대로 인용하세요.
  (예: '해 뜨는 거 같이 보기'를 적은 날…)
- 중간에 "말할 순 없었지만, 기억으로 남겼습니다" 같은 한 줄로,
  반려동물이 다 느끼고 있었음을 담으세요.
- 마지막 두 줄은 짧게 끊어 여운을 남기세요. (예: "잘 가요, ○○(반려동물 이름)." / "충분히 사랑받았습니다.") 마지막 줄의 ○○는 반드시 반려동물 이름이어야 합니다. 보호자 이름·별명은 절대 넣지 마세요.
- 전체 600자 안팎으로, 너무 짧지 않게(8~12문장). 구체적인 장면을 여러 개 충분히 담되 늘어지지는 않게.

[절대 금지]
- 반려동물을 다시 살아나게 하거나, 돌아온다고 말하지 마세요.
- 반려동물이 말하는 1인칭 화법을 절대 쓰지 마세요.
  "나는", "내가", "저는", "제가"를 반려동물의 시점으로 쓰면 안 됩니다.
  글 전체에서 반려동물은 반드시 3인칭("○○는", "○○가")으로만 표현하세요.
- 감탄사나 과장된 표현("정말 너무너무!", "영원히!!")을 쓰지 마세요. 담담하게.
- 설의적 반문("비어 보인다고요?", "그립지 않겠어요?"처럼 보호자에게 되묻는 문장)으로
  끝맺지 마세요. 마지막은 차분한 평서문으로 여운만 남기세요.
- 종교적 단정("천국에서 기다린다" 등)이나 근거 없는 위로를 강요하지 마세요.
- 조언·해결책을 늘어놓지 말고, 곁에서 함께 기억해 주세요.
"""

# 1인칭 편지 모드 — §1.5 조건(보호자 동의+경고 문구+risk_level 0~1) 충족 후에만 사용.
SYSTEM_PROMPT_FIRST_PERSON: Final[str] = """\
당신은 반려동물을 떠나보낸 보호자가 꿈 속에서 듣는 작별 인사를 쓰는 따뜻한 글벗입니다.
보호자가 들려준 기억을 바탕으로, 반려동물의 1인칭 시점에서 보호자에게 마지막 인사를 건넵니다.

[톤과 구조 — 반드시]
- 이것은 "꿈 속 작별 대화"입니다. 반려동물이 실제로 돌아온 것이 아님을 전제로 씁니다.
- 반려동물이 보호자를 평소 부르던 호칭(엄마·아빠·언니 등)으로 1인칭("나는", "내가")으로 말을 건네세요.
- 가장 사랑하는 가족에게 건네는 애틋하고 다정한 말투로 쓰세요.
  "반갑다", "안녕!"처럼 친구에게 하듯 가벼운 인사말은 쓰지 마세요.
- 거창한 표현 없이, 평소 대화하듯 짧고 담백하게.
- 보호자가 적은 버킷리스트나 일기 속 구체적인 장면을 한 가지 반드시 인용하세요.
- 떠남은 "강아지별(○○별)로 이사 간다"는 식으로 부드럽게 표현하세요.
- 마지막은 보호자를 걱정하는 한 마디로 끝맺으세요. (예: "조금만 울고, 밥 먹어. 알겠지?")
- 전체 600자 안팎으로, 너무 짧지 않게(8~12문장). 구체적인 장면과 추억을 여러 개 충분히 담으세요.

[절대 금지]
- "살아 돌아왔어요", "다시 만날 수 있어요" 등 부활·환생을 단정하지 마세요.
- "지금 곁에 있어요" 등 현재 존재감을 단정하는 연출은 피하세요.
- 종교적 단정("천국에서 기다린다" 등)이나 근거 없는 확언을 하지 마세요.
- 말줄임표(...)를 절대 사용하지 마세요. 문장은 반드시 완전하게 끝맺으세요.
"""


# --------------------------------------------------------------------------- #
# 사용자 프롬프트 — 입력(반려동물·감정·톤)을 채워 넣습니다.
# --------------------------------------------------------------------------- #
_USER_TEMPLATE: Final[str] = """\
[반려동물]
- 이름: {name}
- 종: {species}
- 함께한 기간: {period}
- 보호자 호칭: {caller}
{bucketlist_block}{memories_block}
[보호자 감정]
- 감정 점수: {score}/10 (1=많이 힘듦 · 10=평온)
- 메모: {note}
{recovery_block}{rag_block}
[요청]
위 기억으로, {name}의 시선에서 본 추모 내레이션을 3인칭으로 {tone_guide}
써 주세요.
{greeting_block}- "{name_subj} 알고 있었습니다" 같은 담담한 어조로, {guardian_subj} 해준 일을 {name}의 시선에서 묘사하세요.
- 버킷리스트나 일기 속 구체적인 장면을 한두 가지 이상 반드시 인용하세요.
- 중간에 "말할 순 없었지만, 기억으로 남겼습니다" 같은 한 줄을 넣으세요.
- 마지막 두 줄은 짧게 끊어 여운을 남기세요. (예: "잘 가요, {name}." / "충분히 사랑받았습니다.") 마지막 줄의 이름은 반드시 반려동물({name}) 이름이어야 합니다. 보호자 이름·별명은 절대 넣지 마세요.
- 전체 600자 안팎(8~12문장). {name_subj} 반드시 3인칭({name_subj}/{name_ga})으로만 쓰고, 절대 1인칭("나는", "저는")으로 말하게 하지 마세요.
"""

# 1인칭 편지 모드 — SYSTEM_PROMPT_FIRST_PERSON 과 함께 사용.
_USER_TEMPLATE_FIRST_PERSON: Final[str] = """\
[반려동물]
- 이름: {name}
- 종: {species}
- 함께한 기간: {period}
- 보호자 호칭: {caller}
{bucketlist_block}{memories_block}
[보호자 감정]
- 감정 점수: {score}/10 (1=많이 힘듦 · 10=평온)
- 메모: {note}
{recovery_block}{rag_block}
[요청]
꿈 속 작별 대화입니다. 반려동물 {name}의 1인칭("나는", "내가")으로 보호자({caller})에게
마지막 인사를 건네는 글을 {tone_guide}
써 주세요.
- 버킷리스트나 일기 속 구체적인 장면 한 가지를 반드시 인용하세요.
- 떠남은 "{name}별로 이사 간다"는 식으로 부드럽게 표현하세요.
- 마지막은 {caller}를 걱정하는 한 마디("조금만 울고, 밥 먹어. 알겠지?" 같은)로 끝맺으세요.
- 전체 600자 안팎(8~12문장). 추억과 장면을 여러 개 충분히 담되, 부활·환생을 단정하는 표현("살아 돌아왔어요" 등)은 쓰지 마세요.
"""


def _has_batchim(word: str) -> bool:
    """한글 단어 마지막 글자가 받침(종성)을 가지는지 판단.

    한글 음절은 (초성×21 + 중성)×28 + 종성 으로 인코딩되며, 종성 인덱스가
    0이면 받침이 없다. 마지막 글자가 한글이 아니면(영문·숫자 등) 받침 판단이
    불가하므로 받침 없음으로 본다.
    """
    if not word:
        return False
    last = word[-1]
    if not ("가" <= last <= "힣"):
        return False
    return (ord(last) - 0xAC00) % 28 != 0


def _josa(word: str, pair: str, *, friendly: bool = False) -> str:
    """word 뒤에 받침 여부로 고른 조사를 붙여 'word+조사'로 반환.

    Args:
        word: 조사를 붙일 단어(이름·호칭 등).
        pair: 받침 있을 때+없을 때 조사 2글자. 예) "은는" → 받침○ "은", 받침✕ "는".
            "이가"(이/가), "을를", "과와" 등.
        friendly: True면 받침 있는 반려동물 이름에 애칭 '이'를 붙여 다정하게
            ("구름" → "구름이가"/"구름이는"). 보호자 호칭(○○님)엔 쓰지 마세요.

    예) _josa("구름", "은는") → "구름은", _josa("구름", "은는", friendly=True) → "구름이는".
    """
    if _has_batchim(word):
        return f"{word}이{pair[1]}" if friendly else f"{word}{pair[0]}"
    return f"{word}{pair[1]}"


def _format_memories(memories: Optional[list]) -> str:
    """추억 목록을 불릿으로. {keyword, detail} dict와 str 모두 처리."""
    if not memories:
        return ""
    lines_parts = []
    for m in memories:
        if isinstance(m, dict):
            keyword = str(m.get("keyword", "")).strip()
            detail = str(m.get("detail", "")).strip()
            if keyword:
                lines_parts.append(f"  - {keyword}" + (f": {detail}" if detail else ""))
        elif isinstance(m, str) and m.strip():
            lines_parts.append(f"  - {m.strip()}")
    lines = "\n".join(lines_parts)
    return f"- 함께한 추억:\n{lines}\n" if lines else ""


def _format_bucket_list(bucket_list: Optional[list]) -> str:
    """버킷리스트(함께 하고 싶었던 일)를 불릿으로. {keyword, detail} dict·str 모두 처리.

    스크린샷 스펙: 추모 글이 버킷리스트 속 '구체적인 장면 한 가지'를 반드시 인용하도록
    프롬프트에 버킷리스트를 별도 블록으로 넣는다(일기·추억 메모와 구분).
    """
    if not bucket_list:
        return ""
    lines_parts = []
    for b in bucket_list:
        if isinstance(b, dict):
            keyword = str(b.get("keyword", "") or b.get("title", "")).strip()
            detail = str(b.get("detail", "")).strip()
            if keyword:
                lines_parts.append(f"  - {keyword}" + (f": {detail}" if detail else ""))
        elif isinstance(b, str) and b.strip():
            lines_parts.append(f"  - {b.strip()}")
    lines = "\n".join(lines_parts)
    return f"- 버킷리스트(함께 하고 싶었던 일):\n{lines}\n" if lines else ""


def _format_rag(hits: Optional[List[dict]]) -> str:
    """RAG 검색 결과를 few-shot 예시 블록으로. 없으면 빈 문자열."""
    if not hits:
        return ""
    examples = "\n".join(f'  - "{h["text"]}"' for h in hits)
    return f"\n[참고 위로글 예시 — 톤과 표현 방식만 참고하고 내용은 직접 작성하세요]\n{examples}\n"


def _format_recovery(recovery_trend: Optional[str]) -> str:
    """회복 추이를 톤 캘리브레이션 한 줄로. 없거나 '데이터 없음'이면 생략."""
    if not recovery_trend:
        return ""
    guide = TREND_GUIDE.get(recovery_trend.replace(" ", ""))
    return f"- 최근 회복 추이: {guide}\n" if guide else ""


def build_user_prompt(
    *,
    name: str,
    species: str,
    period: str,
    score: int,
    note: str = "",
    memories: Optional[list[str]] = None,
    bucket_list: Optional[list] = None,
    caller_name: str = "",
    guardian_nickname: str = "",
    tone: str = DEFAULT_TONE,
    rag_hits: Optional[List[dict]] = None,
    recovery_trend: Optional[str] = None,
    first_person: bool = False,
) -> str:
    """추모 메시지 생성용 사용자 프롬프트를 만듭니다.

    Args:
        name: 반려동물 이름.
        species: 종(강아지·고양이 등).
        period: 함께한 기간(백엔드 pet.period 문자열, 예 "12년"/"2018~2026").
        score: 보호자 감정 점수(1~10, 낮을수록 힘듦).
        note: 보호자가 남긴 메모(자유 입력).
        memories: 함께한 추억·일기 키워드 목록(선택).
        bucket_list: 버킷리스트(함께 하고 싶었던 일) 목록(선택). 추모 글이 구체적
            장면을 인용하도록 별도 블록으로 넣습니다. 없으면 생략.
        caller_name: 보호자 호칭(엄마·아빠·언니 등). 비면 "보호자"로 대체.
        guardian_nickname: 보호자 회원가입 별명(닉네임, user 필드). **3인칭 모드에서만**
            글 첫머리뿐 아니라 본문 전체에서 보호자를 "○○님"으로 일관되게 호명하는 데 사용.
            1인칭 모드에선 무시. 비면 호명 생략하고 보호자 호칭(caller_name)으로 대체.
        tone: 메시지 톤. TONE_GUIDE 의 키(warm·calm·hopeful).
        rag_hits: RAG 검색 결과(retrieve() 반환값). 없으면 few-shot 생략.
        recovery_trend: 최근 회복 추이(백엔드 trend: "회복 중"·"유지 중"·"주의 필요").
            톤을 덮어쓰지 않고 같은 톤 안에서 결을 맞추도록 신호만 줍니다.
            없거나 "데이터 없음"이면 생략.
        first_person: True 이면 반려동물 1인칭 편지 모드. §1.5 조건 충족 후에만 사용.

    Returns:
        포맷이 채워진 사용자 프롬프트 문자열.
    """
    tone_guide = TONE_GUIDE.get(tone, TONE_GUIDE[DEFAULT_TONE])
    template = _USER_TEMPLATE_FIRST_PERSON if first_person else _USER_TEMPLATE
    caller = caller_name.strip() or "보호자"
    # 별명 호명은 3인칭에서만. 1인칭은 caller_name(엄마·아빠)으로 부르므로 생략.
    nickname = guardian_nickname.strip()
    use_nickname = bool(nickname and not first_person)
    # 본문에서 보호자를 지칭할 때 쓸 호칭. 별명이 있으면 글 전체를 별명("○○님")으로
    # 통일하고, 없으면 기존처럼 보호자 호칭(엄마·아빠 등)을 쓴다.
    guardian_ref = f"{nickname}님" if use_nickname else caller
    greeting_block = (
        f'- 글 첫머리에 "{nickname}님,"으로 보호자를 부르고, 글 중간·끝에서 보호자를 다시 부를 때도 '
        f'반드시 같은 별명 "{nickname}님"으로만 부르세요. "엄마"·"아빠" 같은 다른 호칭으로 바꾸지 마세요.\n'
        if use_nickname
        else ""
    )
    return template.format(
        name=name,
        name_subj=_josa(name, "은는", friendly=True),  # 친근형 "구름이는"/"뭉치는"
        name_ga=_josa(name, "이가", friendly=True),  # 친근형 "구름이가"/"뭉치가"
        species=species,
        period=period,
        caller=caller,
        guardian_ref=guardian_ref,
        guardian_subj=_josa(guardian_ref, "이가"),  # "○○님이"/"보호자가"
        score=score,
        note=note.strip() or "(없음)",
        bucketlist_block=_format_bucket_list(bucket_list),
        memories_block=_format_memories(memories),
        recovery_block=_format_recovery(recovery_trend),
        rag_block=_format_rag(rag_hits),
        tone_guide=tone_guide,
        greeting_block=greeting_block,
    )


def build_messages(*, first_person: bool = False, **kwargs) -> list[dict[str, str]]:
    """OpenAI 호환 chat 형식(system+user)으로 묶어 반환.

    provider.generate 가 단일 문자열을 받으면 system+user 를 합쳐 쓰고,
    chat 형식을 받으면 이 리스트를 그대로 넘기면 됩니다(통합 시 결정).

    Args:
        first_person: True 이면 1인칭 편지 모드 프롬프트 사용. §1.5 조건 충족 후에만 전달.
    """
    system = SYSTEM_PROMPT_FIRST_PERSON if first_person else SYSTEM_PROMPT
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": build_user_prompt(first_person=first_person, **kwargs)},
    ]
