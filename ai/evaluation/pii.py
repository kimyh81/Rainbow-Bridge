"""보호자·반려동물 **PII 비식별** — LLM 전송/로그 저장 **전** 원문 마스킹.

[logs.py](logs.py) 와 같은 철학: 원문·개인정보를 외부(LLM API)나 저장소에 그대로
남기지 않는다. 단, logs.py 가 "원문을 아예 안 담는" 쪽이라면, 이 모듈은 **원문을
넘겨야 하는 곳**(위기 분류·메시지 생성처럼 텍스트 자체가 입력인 경우)에서
**식별 정보만 가린 텍스트**를 만들어 주는 순수 함수다.

흐름(주입식 — 호출부가 1줄 끼움):
    note(원문) ─▶ redact(note, pet_names=, owner_names=) ─▶ 가린 텍스트 ─▶ LLM/DB

신뢰도 경계 (중요 — 과약속 금지):
    - **알려진 이름**(반려동물·보호자, pet/user 레코드에서 옴) = 정확 문자열 치환 →
      **확실히** 제거.
    - **자유기입 PII**(전화·이메일 등) = best-effort 정규식 → **완전 보장 아님**.
      주소·생년월일 같은 비정형은 못 잡는다. "known-name 확실 + 그 외 best-effort"
      라고만 약속한다.

호출 지점(핸드오프 대상):
    - `backend/app/services/emotion.py`  — note 를 DB 저장·assess_crisis 전 (모세종)
    - `backend/app/services/message.py`  — note·pet 이름을 generate 전 (모세종)
    - `ai/llm/safety.py` · `provider.py`  — LLM 호출 직전 (반소람)
"""

from __future__ import annotations

import re
import unicodedata
from typing import Final, Iterable, Optional

# 치환 라벨 — 가린 자리에 남길 표식(사람이 읽어 맥락은 유지, 식별은 불가).
LABEL_PET: Final[str] = "[반려동물]"
LABEL_OWNER: Final[str] = "[보호자]"
LABEL_CONTACT: Final[str] = "[연락처]"

# best-effort 연락처 패턴 (자유기입 한계 — 완전 보장 ❌)
#   전화: 010-1234-5678 / 01012345678 / 010.1234.5678 / 02-123-4567 등
#   숫자 경계는 \b 대신 (?<!\d)/(?!\d) 로 — 한글은 \w 라 "전화010..." 처럼
#   한글 바로 뒤 번호에서 \b 가 무력해지는 누출을 막는다.
#   이메일: 표준 local@domain
_PHONE_RE: Final[re.Pattern[str]] = re.compile(
    r"(?<!\d)0\d{1,2}[-.\s]?\d{3,4}[-.\s]?\d{4}(?!\d)"
)
_EMAIL_RE: Final[re.Pattern[str]] = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")


def _nfc(text: str) -> str:
    """유니코드 NFC 정규화 — 조합형(NFD)/완성형(NFC) 표기 차이를 흡수.

    DB 이름이 NFC 인데 노트가 NFD 면 ``replace``/regex 가 못 잡고 이름이 누출된다
    (macOS 파일명·일부 IME 가 NFD 생성). 양쪽을 NFC 로 통일해 비교한다.
    """
    return unicodedata.normalize("NFC", text)


def _clean_names(names: Iterable[str]) -> list[str]:
    """빈 값·중복 제거 + NFC 정규화 후 **긴 이름부터** 정렬.

    긴 이름을 먼저 치환해야 짧은 이름이 긴 이름의 부분과 겹쳐 깨지지 않는다
    (예: '봄','봄이' 동시 등록 시 '봄이'부터). ``names`` 에 문자열 하나를 직접
    넘기면 글자 단위 순회가 되어 오작동하므로 단일 문자열은 1-튜플로 감싼다.
    """
    if isinstance(names, str):
        names = (names,)
    seen = {_nfc(n.strip()) for n in names if n and n.strip()}
    return sorted(seen, key=len, reverse=True)


def redact_names(text: str, names: Iterable[str], label: str) -> str:
    """``names`` 의 이름을 ``label`` 로 치환(대소문자 무시·NFC).

    알려진 이름은 **확실히** 제거한다(영문 펫 이름의 대소문자 변형 'Coco'/'coco'
    포함). 다만 한글은 단어 경계(``\\b``)가 없어, **1~2글자 이름은 합성어
    내부까지 치환될 수 있다**(예: '봄'→'봄날'의 '봄'). 호출부는 실제 등록명
    (보통 2자+)을 넘기는 전제이며, 이 합성어 오탐은 best-effort 한계다.
    """
    text = _nfc(text)
    for name in _clean_names(names):
        text = re.sub(re.escape(name), label, text, flags=re.IGNORECASE)
    return text


def redact_contacts(text: str) -> str:
    """전화·이메일 등 연락처를 ``LABEL_CONTACT`` 로 가린다(best-effort).

    이메일을 먼저 가린 뒤 전화 패턴을 적용한다(이메일 안 숫자 오인 방지).
    """
    text = _EMAIL_RE.sub(LABEL_CONTACT, text)
    text = _PHONE_RE.sub(LABEL_CONTACT, text)
    return text


def redact(
    text: Optional[str],
    *,
    pet_names: Iterable[str] = (),
    owner_names: Iterable[str] = (),
    mask_contacts: bool = True,
) -> str:
    """원문에서 식별 정보를 가린 텍스트를 돌려준다(순수 함수).

    Args:
        text: 원문. None·빈 문자열이면 "" 반환(graceful).
        pet_names: 반려동물 이름들(pet 레코드) → ``[반려동물]``.
        owner_names: 보호자 이름들(user 레코드) → ``[보호자]``.
        mask_contacts: 전화·이메일 best-effort 마스킹 여부.

    Returns:
        가린 텍스트. **알려진 이름은 확실히 제거**(대소문자·NFC 변형 포함),
        연락처는 best-effort. 자유기입 비정형 PII(주소 등)·1~2글자 이름의
        합성어 오탐은 가리거나 막지 못할 수 있다.
    """
    if not isinstance(text, str) or not text:
        return ""
    text = redact_names(text, pet_names, LABEL_PET)
    text = redact_names(text, owner_names, LABEL_OWNER)
    if mask_contacts:
        text = redact_contacts(text)
    return text
