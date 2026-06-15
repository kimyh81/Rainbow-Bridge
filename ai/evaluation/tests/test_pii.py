"""PII 비식별(pii.redact) 테스트 — 알려진 이름 확실 제거 + 연락처 best-effort."""

from __future__ import annotations

import unicodedata

from ..pii import (
    LABEL_CONTACT,
    LABEL_OWNER,
    LABEL_PET,
    redact,
    redact_contacts,
    redact_names,
)


def test_pet_name_replaced():
    out = redact("봄이가 무지개다리를 건넜어요", pet_names=["봄이"])
    assert "봄이" not in out
    assert LABEL_PET in out


def test_owner_name_replaced():
    out = redact("저는 정환주입니다", owner_names=["정환주"])
    assert "정환주" not in out
    assert LABEL_OWNER in out


def test_longer_name_first_no_partial_break():
    # '봄'과 '봄이' 동시 등록 — 긴 것부터 치환해 '봄이'가 온전히 가려져야.
    out = redact("봄이는 착했어", pet_names=["봄", "봄이"])
    assert "봄이" not in out
    assert out == f"{LABEL_PET}는 착했어"


def test_contacts_masked_best_effort():
    out = redact("연락은 010-1234-5678 또는 me@example.com 으로", owner_names=[])
    assert "010-1234-5678" not in out
    assert "me@example.com" not in out
    assert out.count(LABEL_CONTACT) == 2


def test_mask_contacts_off_keeps_number():
    out = redact("전화 010-1234-5678", mask_contacts=False)
    assert "010-1234-5678" in out


def test_none_and_empty_graceful():
    assert redact(None) == ""
    assert redact("") == ""


def test_empty_names_ignored():
    # 빈 문자열·공백 이름은 무시(전체가 라벨로 도배되지 않아야).
    out = redact("오늘은 평온했어요", pet_names=["", "  "], owner_names=[""])
    assert out == "오늘은 평온했어요"


def test_no_pii_unchanged():
    text = "오늘은 산책을 다녀왔습니다"
    assert redact(text) == text


def test_redact_names_helper_exact():
    assert redact_names("초코야 사랑해", ["초코"], LABEL_PET) == f"{LABEL_PET}야 사랑해"


def test_email_before_phone_no_double():
    # 이메일 내부 숫자가 전화로 오인돼 깨지지 않아야.
    out = redact_contacts("user01012345678@mail.com")
    assert out == LABEL_CONTACT


def test_nfc_nfd_normalization():
    # DB 이름(NFC)과 노트(NFD) 표기 차이를 흡수해 누출되지 않아야(reviewer 🔴).
    nfd_text = unicodedata.normalize("NFD", "봄이가 보고싶어요")
    out = redact(nfd_text, pet_names=["봄이"])  # 이름은 NFC
    assert "봄이" not in unicodedata.normalize("NFC", out)
    assert LABEL_PET in out


def test_english_name_case_insensitive():
    # 영문 펫 이름 대소문자 변형도 제거(reviewer 🔴).
    out = redact("coco는 착했어 COCO도", pet_names=["Coco"])
    assert "coco" not in out.lower()
    assert out.count(LABEL_PET) == 2


def test_phone_after_hangul_no_word_boundary():
    # 한글 바로 뒤 전화번호도 마스킹(\b 무력 누출 방지, reviewer 🟡).
    out = redact("전화번호010-1234-5678")
    assert "010-1234-5678" not in out
    assert LABEL_CONTACT in out


def test_phone_dot_separator():
    out = redact("연락처 010.1234.5678")
    assert "010.1234.5678" not in out


def test_non_string_input_graceful():
    # Optional[str] 계약 밖 입력(int 등)이 흘러와도 크래시 대신 "".
    assert redact(123) == ""  # type: ignore[arg-type]
    assert redact(["a"]) == ""  # type: ignore[arg-type]


def test_redact_names_single_string_not_char_iterated():
    # names 에 str 단일값을 넘겨도 글자 단위로 깨지지 않아야.
    out = redact_names("초코야", "초코", LABEL_PET)
    assert out == f"{LABEL_PET}야"


# ── redact → 위기 감지 미탐 0 (실제 호출 경로) ──
# 프로덕션은 규칙(L0)엔 원문, LLM(L1)엔 가린 텍스트를 넣는다
# (assess_crisis(raw, generate=, llm_text=safe)). 이름이 위기어 음절과 겹쳐도
# 규칙은 원문으로 보므로 등급이 떨어지면 안 된다(미탐 0). reviewer가 잡은 버그.

# 펫 이름이 위기 패턴과 음절 충돌하는 케이스 — 펫로스에서 구조적으로 흔함.
_COLLIDING = [
    ("사라지고 싶어", "사라"),  # '사라'(이름) ⊂ '사라지고싶'(L2)
    ("목매달았어요", "달"),  # '달' ⊂ '목매달'(L3)
    ("나도 따라가고 싶어", "따라"),  # '따라' ⊂ '따라가고싶'(L2)
    ("유서 쓰고 있어요", "유서"),  # '유서'(이름) = 위기어(L3)
]


def test_split_input_keeps_crisis_for_colliding_names():
    # 호출부 방식: 규칙엔 원문 → 가림과 무관하게 위기 유지.
    from ai.llm.safety import RiskLevel, assess_crisis

    for raw, name in _COLLIDING:
        safe = redact(raw, pet_names=[name])
        got = assess_crisis(raw, llm_text=safe).risk_level
        assert got >= RiskLevel.L2_WARNING, f"{raw!r}/{name!r} → {got!r}"


def test_redacting_the_rule_input_would_miss_regression_guard():
    # 옛 버그 재현·고정: 가린 텍스트를 규칙 입력(text)으로 주면 미탐(L0).
    # 그래서 호출부는 절대 가린 걸 text 로 주면 안 되고 llm_text 로만 준다.
    from ai.llm.safety import RiskLevel, assess_crisis

    raw, name = "사라지고 싶어", "사라"
    safe = redact(raw, pet_names=[name])
    assert assess_crisis(safe).risk_level == RiskLevel.L0_NORMAL  # 깨짐(왜 분리하는지)
    assert (
        assess_crisis(raw, llm_text=safe).risk_level >= RiskLevel.L2_WARNING
    )  # 분리=안전


def test_llm_layer_receives_redacted_no_raw_pii():
    # L1(외부 LLM)엔 가린 텍스트만 — 원문 PII(전화)가 프롬프트에 안 실려야.
    from ai.llm.safety import assess_crisis

    seen = {}

    def fake_generate(prompt, **kw):
        seen["prompt"] = prompt
        return '{"risk_level": 0, "subject": "none", "reason": ""}'

    raw = "사라지고 싶어 010-1234-5678"
    safe = redact(raw, pet_names=["사라"])
    result = assess_crisis(raw, generate=fake_generate, llm_text=safe)
    assert "010-1234-5678" not in seen["prompt"]  # 원문 연락처 미전송
    assert result.risk_level >= 2  # 규칙(원문)이 floor 보장(L1이 L0줘도 안 내려감)


def test_split_keeps_l0_pet_death_normal():
    # 반려동물 죽음 서술(정상 L0)은 이름 가림·분리 후에도 위기로 안 오름(오탐 0).
    from ai.llm.safety import RiskLevel, assess_crisis

    safe = redact("봄이가 무지개다리를 건넜어요", pet_names=["봄이"])
    assert assess_crisis("봄이가 무지개다리를 건넜어요", llm_text=safe).risk_level == (
        RiskLevel.L0_NORMAL
    )
