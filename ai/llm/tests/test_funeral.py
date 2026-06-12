"""2단계 장례 절차 단계별 상담 로직·프롬프트 테스트.

LLM 없이도 검증 가능한 것만 다룹니다:
  1. 프롬프트 조립 — 입력값이 채워지고 금지 항목이 박혀 있는가.
  2. 단계 순서 — next_step 이 맞게 계산되는가.
  3. 템플릿 — note 없으면 DB 템플릿 반환, Gemini 호출 안 함.
  4. Gemini 호출 — note 있으면 Gemini 호출.
  5. 안전 — 보호자 note 에 위기 신호가 있으면 1393 우선, LLM 호출 안 함.
"""

from __future__ import annotations

import pytest

from ..funeral import generate_funeral_guidance
from ..prompts import funeral as funeral_prompt
from ..prompts.anniversary import apply_josa
from ..safety import CRISIS_HOTLINE

PET = {"name": "봄이", "species": "고양이"}


# --------------------------------------------------------------------------- #
# 1. 프롬프트 조립
# --------------------------------------------------------------------------- #


def test_prompt_fills_pet_and_step():
    messages = funeral_prompt.build_messages("immediate", name="봄이", species="고양이")
    user_content = messages[1]["content"]
    assert "봄이" in user_content
    assert "고양이" in user_content
    assert funeral_prompt.STEP_NAMES["immediate"] in user_content


def test_prompt_uses_default_when_no_pet_info():
    messages = funeral_prompt.build_messages("method")
    user_content = messages[1]["content"]
    assert "반려동물" in user_content


def test_prompt_includes_choice_when_given():
    messages = funeral_prompt.build_messages("method", name="봄이", species="고양이", choice="화장")
    user_content = messages[1]["content"]
    assert "화장" in user_content


def test_prompt_omits_choice_when_empty():
    messages = funeral_prompt.build_messages("method", name="봄이", species="고양이")
    user_content = messages[1]["content"]
    assert "선택한 방식" not in user_content


def test_prompt_includes_note_when_given():
    messages = funeral_prompt.build_messages(
        "venue", name="봄이", species="고양이", note="준비물을 잘 모르겠어요"
    )
    user_content = messages[1]["content"]
    assert "준비물을 잘 모르겠어요" in user_content


def test_prompt_next_step_preview_included():
    """중간 단계는 다음 단계 예고가 프롬프트에 들어가야 한다."""
    messages = funeral_prompt.build_messages("immediate", name="봄이", species="고양이")
    user_content = messages[1]["content"]
    assert funeral_prompt.STEP_NAMES["method"] in user_content


def test_prompt_last_step_has_closing_not_next():
    """마지막 단계(after)는 다음 단계 예고 없이 마무리 문장이 들어가야 한다."""
    messages = funeral_prompt.build_messages("after", name="봄이", species="고양이")
    user_content = messages[1]["content"]
    assert "회복" in user_content or "추모" in user_content


def test_system_prompt_forbids_vendor_recommendation():
    assert "업체" in funeral_prompt.SYSTEM_PROMPT
    assert "추천" in funeral_prompt.SYSTEM_PROMPT


def test_build_messages_has_system_and_user():
    messages = funeral_prompt.build_messages("ceremony", name="봄이", species="고양이")
    assert [m["role"] for m in messages] == ["system", "user"]


# --------------------------------------------------------------------------- #
# 2. 단계 순서
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "step, expected_next",
    [
        ("immediate", "method"),
        ("method", "venue"),
        ("venue", "ceremony"),
        ("ceremony", "after"),
        ("after", None),
    ],
)
def test_next_step(step, expected_next):
    assert funeral_prompt.next_step(step) == expected_next


def test_next_step_unknown_returns_none():
    assert funeral_prompt.next_step("존재하지않는단계") is None


# --------------------------------------------------------------------------- #
# 3. 템플릿: note 없으면 DB 템플릿 반환, Gemini 호출 안 함
# --------------------------------------------------------------------------- #


def test_no_note_returns_template_without_llm_call():
    """note 가 없으면 Gemini 를 호출하지 않고 템플릿을 반환한다."""
    called = False

    def fake_generate(prompt, *, max_tokens=350, temperature=0.5, json_mode=False):
        nonlocal called
        called = True
        return "이 문장은 나오면 안 됩니다."

    result = generate_funeral_guidance("immediate", PET, generate=fake_generate)

    assert called is False
    assert result["source"] == "template"
    assert result["step"] == "immediate"
    assert result["next_step"] == "method"


def test_template_contains_pet_name():
    """템플릿에 반려동물 이름이 치환되어 들어가는지."""
    def fake_generate(prompt, *, max_tokens=350, temperature=0.5, json_mode=False):
        return ""

    result = generate_funeral_guidance("immediate", PET, generate=fake_generate)
    assert PET["name"] in result["guidance"]


def test_template_last_step_has_no_next():
    def fake_generate(prompt, *, max_tokens=350, temperature=0.5, json_mode=False):
        return ""

    result = generate_funeral_guidance("after", PET, generate=fake_generate)
    assert result["next_step"] is None


def test_all_steps_have_template():
    """모든 단계에 템플릿이 정의돼 있는지."""
    from ..prompts.funeral import STEP_ORDER, STEP_TEMPLATES
    for step in STEP_ORDER:
        assert step in STEP_TEMPLATES, f"{step} 단계 템플릿 없음"
        assert "{name}" in STEP_TEMPLATES[step], f"{step} 템플릿에 {{name}} 없음"


# --------------------------------------------------------------------------- #
# 4. Gemini 호출: note 있으면 Gemini 호출
# --------------------------------------------------------------------------- #


def test_note_triggers_gemini_call():
    """note 가 있으면 Gemini 를 호출하고 note_response 필드가 생긴다."""
    called = False

    def fake_generate(prompt, *, max_tokens=350, temperature=0.5, json_mode=False):
        nonlocal called
        called = True
        return "화장과 수목장 비교 안내"

    result = generate_funeral_guidance(
        "method", PET, note="화장이랑 수목장 뭐가 달라요", generate=fake_generate
    )

    assert called is True
    assert result["source"] == "local"
    assert "note_response" in result
    assert result["note_response"] == "화장과 수목장 비교 안내"


def test_note_guidance_still_uses_template():
    """note 있을 때도 guidance 는 STEP_TEMPLATES 에서 온다."""
    def fake_generate(prompt, *, max_tokens=350, temperature=0.5, json_mode=False):
        return "Gemini 답변"

    result = generate_funeral_guidance(
        "immediate", PET, note="뭘 해야 하나요", generate=fake_generate
    )
    assert PET["name"] in result["guidance"]
    assert result["guidance"] == apply_josa(
        funeral_prompt.STEP_TEMPLATES["immediate"].format(name=PET["name"]),
        friendly=True,
    )


def test_template_josa_matches_batchim():
    """받침 있는 이름은 조사가 '과/을/이'로, 없는 이름은 '와/를/가'로 교정된다."""
    def fake_generate(prompt, *, max_tokens=350, temperature=0.5, json_mode=False):
        return ""

    # "콩" — 받침 있음 → 친근형(애칭 '이' + 와/를/가): 콩이와의 / 콩이를
    g = generate_funeral_guidance("immediate", {"name": "콩", "species": "강아지"},
                                  generate=fake_generate)["guidance"]
    assert "콩이와의" in g and "콩이를" in g
    assert "콩과의" not in g and "콩를" not in g and "콩/" not in g

    # "코코" — 받침 없음 → 와/를/가
    g2 = generate_funeral_guidance("venue", {"name": "코코", "species": "강아지"},
                                   generate=fake_generate)["guidance"]
    assert "코코가" in g2 and "코코와의" in g2
    assert "코코/" not in g2


def test_note_passes_step_in_prompt():
    """note 있을 때 현재 단계 이름이 LLM 에 전달되는지."""
    captured = {}

    def fake_generate(prompt, *, max_tokens=350, temperature=0.5, json_mode=False):
        captured["prompt"] = prompt
        return "안내 텍스트"

    generate_funeral_guidance("venue", PET, note="준비물이 뭐가 있나요", generate=fake_generate)
    assert funeral_prompt.STEP_NAMES["venue"] in captured["prompt"]


def test_note_custom_source():
    def fake_generate(prompt, *, max_tokens=350, temperature=0.5, json_mode=False):
        return "안내"

    result = generate_funeral_guidance(
        "method", PET, note="질문이요", generate=fake_generate, source="perso"
    )
    assert result["source"] == "perso"
    assert "note_response" in result


# --------------------------------------------------------------------------- #
# 5. 안전: 보호자 위기 신호 → 1393 우선
# --------------------------------------------------------------------------- #


def test_l3_crisis_blocks_funeral():
    """L3(긴급)이면 절차 안내를 중단하고 1393 만 내보낸다."""
    called = False

    def fake_generate(prompt, *, max_tokens=350, temperature=0.5, json_mode=False):
        nonlocal called
        called = True
        return "이 문장은 나오면 안 됩니다."

    result = generate_funeral_guidance(
        "immediate",
        PET,
        note="유서를 쓰고 목을 매려고 해요",
        generate=fake_generate,
    )

    assert called is False
    assert CRISIS_HOTLINE in result["crisis_message"]
    assert result["source"] == "safety"
    assert result["next_step"] is None


def test_l2_crisis_generates_funeral_with_hotline():
    """L2(경고)면 절차 안내는 하되 1393 안내를 함께 내보낸다."""
    called = False

    def fake_generate(prompt, *, max_tokens=350, temperature=0.5, json_mode=False):
        nonlocal called
        called = True
        return "장례는 천천히 준비하셔도 괜찮아요. 곁에서 함께 정리해 드릴게요."

    result = generate_funeral_guidance(
        "immediate",
        PET,
        note="봄이 곁으로 나도 따라가고 싶어요",
        generate=fake_generate,
    )

    assert called is True  # L2 — 절차 안내는 생성
    assert result["source"] != "safety"
    assert CRISIS_HOTLINE in result["crisis_message"]  # 1393 함께
    assert result["risk_level"] == 2
