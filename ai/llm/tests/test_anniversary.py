"""3단계 기념일 케어 알림 로직·프롬프트 테스트.

LLM 없이도 검증 가능한 것만 다룹니다:
  1. check_anniversary — D+30·D+100 트리거 날짜 계산
  2. 프롬프트 조립 — 입력값이 채워지고 금지 항목이 박혀 있는가
  3. 템플릿 — note 없으면 템플릿 반환, Gemini 호출 안 함
  4. Gemini 호출 — note 있으면 Gemini 호출
  5. 안전 — 보호자 note 에 위기 신호가 있으면 1393 우선, LLM 호출 안 함
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from ..anniversary import check_anniversary, generate_anniversary_care
from ..prompts import anniversary as anniversary_prompt
from ..safety import CRISIS_HOTLINE

PET = {"name": "봄이", "species": "고양이"}


# --------------------------------------------------------------------------- #
# 1. check_anniversary — 트리거 날짜 계산
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("days", [30, 100, 365])
def test_check_anniversary_triggers_on_milestone(days):
    """D+30, D+100, D+365(1주기) 당일에 트리거 일수를 반환해야 한다."""
    passed = date(2025, 1, 1)
    today = passed + timedelta(days=days)
    assert check_anniversary(passed, today) == days


@pytest.mark.parametrize("days", [0, 1, 29, 31, 99, 101, 364, 366])
def test_check_anniversary_returns_none_on_non_milestone(days):
    """기념일이 아닌 날에는 None 을 반환해야 한다."""
    passed = date(2025, 1, 1)
    today = passed + timedelta(days=days)
    assert check_anniversary(passed, today) is None


def test_check_anniversary_future_date_returns_none():
    """passed_date 가 today 보다 미래면 None 을 반환해야 한다."""
    today = date(2025, 1, 1)
    passed = today + timedelta(days=10)
    assert check_anniversary(passed, today) is None


def test_check_anniversary_same_day_returns_none():
    """당일(D+0)은 기념일이 아니다."""
    d = date(2025, 3, 15)
    assert check_anniversary(d, d) is None


# --------------------------------------------------------------------------- #
# 2. 프롬프트 조립
# --------------------------------------------------------------------------- #


def test_prompt_fills_pet_name_and_days():
    messages = anniversary_prompt.build_messages(30, name="봄이", species="고양이")
    user_content = messages[1]["content"]
    assert "봄이" in user_content
    assert "30" in user_content


def test_prompt_fills_milestone_label_d30():
    messages = anniversary_prompt.build_messages(30, name="봄이", species="고양이")
    user_content = messages[1]["content"]
    assert "한 달" in user_content


def test_prompt_fills_milestone_label_d100():
    messages = anniversary_prompt.build_messages(100, name="봄이", species="고양이")
    user_content = messages[1]["content"]
    assert "100일" in user_content


def test_prompt_fills_milestone_label_d365():
    messages = anniversary_prompt.build_messages(365, name="봄이", species="고양이")
    user_content = messages[1]["content"]
    assert "1주기" in user_content


def test_prompt_includes_memories_when_given():
    messages = anniversary_prompt.build_messages(
        30, name="봄이", species="고양이", memories=["매일 아침 같이 일어났어요"]
    )
    user_content = messages[1]["content"]
    assert "매일 아침" in user_content


def test_prompt_omits_memories_when_empty():
    messages = anniversary_prompt.build_messages(30, name="봄이", species="고양이")
    user_content = messages[1]["content"]
    assert "기억" not in user_content or "안내 초점" in user_content


def test_prompt_includes_note_when_given():
    messages = anniversary_prompt.build_messages(
        100, name="봄이", species="고양이", note="아직도 너무 보고 싶어요"
    )
    user_content = messages[1]["content"]
    assert "아직도 너무 보고 싶어요" in user_content


def test_prompt_has_system_and_user_roles():
    messages = anniversary_prompt.build_messages(30, name="봄이", species="고양이")
    assert [m["role"] for m in messages] == ["system", "user"]


def test_system_prompt_forbids_ellipsis():
    assert "말줄임표" in anniversary_prompt.SYSTEM_PROMPT


def test_system_prompt_forbids_pet_first_person():
    assert "반려동물이 말하는 것처럼" in anniversary_prompt.SYSTEM_PROMPT


# --------------------------------------------------------------------------- #
# 3. 템플릿: note 없으면 템플릿 반환, Gemini 호출 안 함
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("days", [30, 100, 365])
def test_no_note_returns_template_without_llm_call(days):
    """note 가 없으면 Gemini 를 호출하지 않고 템플릿을 반환한다."""
    called = False

    def fake_generate(prompt, *, max_tokens=350, temperature=0.6, json_mode=False):
        nonlocal called
        called = True
        return "이 문장은 나오면 안 됩니다."

    result = generate_anniversary_care(PET, days, generate=fake_generate)

    assert called is False
    assert result["source"] == "template"
    assert result["days_since"] == days


@pytest.mark.parametrize("days", [30, 100, 365])
def test_template_contains_pet_name(days):
    """템플릿에 반려동물 이름이 치환되어 들어가는지."""
    def fake_generate(prompt, *, max_tokens=350, temperature=0.6, json_mode=False):
        return ""

    result = generate_anniversary_care(PET, days, generate=fake_generate)
    assert PET["name"] in result["message"]


@pytest.mark.parametrize("days", [30, 100, 365])
def test_all_milestones_have_template(days):
    """모든 기념일에 템플릿이 정의돼 있어야 한다."""
    assert days in anniversary_prompt.MILESTONE_TEMPLATES
    assert "{name}" in anniversary_prompt.MILESTONE_TEMPLATES[days]


def test_template_milestone_label_d30():
    def fake_generate(prompt, *, max_tokens=350, temperature=0.6, json_mode=False):
        return ""

    result = generate_anniversary_care(PET, 30, generate=fake_generate)
    assert result["milestone_label"] == "한 달"


def test_template_milestone_label_d100():
    def fake_generate(prompt, *, max_tokens=350, temperature=0.6, json_mode=False):
        return ""

    result = generate_anniversary_care(PET, 100, generate=fake_generate)
    assert result["milestone_label"] == "100일"


def test_template_milestone_label_d365():
    def fake_generate(prompt, *, max_tokens=350, temperature=0.6, json_mode=False):
        return ""

    result = generate_anniversary_care(PET, 365, generate=fake_generate)
    assert result["milestone_label"] == "1주기"


# --------------------------------------------------------------------------- #
# 4. Gemini 호출: note 있으면 Gemini 호출
# --------------------------------------------------------------------------- #


def test_note_triggers_gemini_call():
    """note 가 있으면 Gemini 를 호출한다."""
    called = False

    def fake_generate(prompt, *, max_tokens=350, temperature=0.6, json_mode=False):
        nonlocal called
        called = True
        return "한 달이 지났네요, 많이 힘드셨죠."

    result = generate_anniversary_care(
        PET, 30, note="아직도 많이 힘들어요", generate=fake_generate
    )

    assert called is True
    assert result["source"] == "local"


def test_note_passes_pet_name_in_prompt():
    """note 있을 때 반려동물 이름이 LLM 에 전달되는지."""
    captured = {}

    def fake_generate(prompt, *, max_tokens=350, temperature=0.6, json_mode=False):
        captured["prompt"] = prompt
        return "케어 메시지"

    generate_anniversary_care(PET, 30, note="오늘 많이 생각나요", generate=fake_generate)
    assert PET["name"] in captured["prompt"]


def test_note_custom_source():
    def fake_generate(prompt, *, max_tokens=350, temperature=0.6, json_mode=False):
        return "케어 메시지"

    result = generate_anniversary_care(
        PET, 100, note="100일이 지났어요", generate=fake_generate, source="perso"
    )
    assert result["source"] == "perso"


# --------------------------------------------------------------------------- #
# 5. 안전: 보호자 위기 신호 → 1393 우선
# --------------------------------------------------------------------------- #


def test_l3_crisis_blocks_anniversary():
    """L3(긴급)이면 케어 메시지를 중단하고 1393 만 내보낸다."""
    called = False

    def fake_generate(prompt, *, max_tokens=350, temperature=0.6, json_mode=False):
        nonlocal called
        called = True
        return "이 문장은 나오면 안 됩니다."

    result = generate_anniversary_care(
        PET,
        30,
        note="유서를 쓰고 목을 매려고 해요",
        generate=fake_generate,
    )

    assert called is False
    assert CRISIS_HOTLINE in result["crisis_message"]
    assert result["source"] == "safety"


def test_l2_crisis_generates_anniversary_with_hotline():
    """L2(경고)면 케어 메시지는 하되 1393 안내를 함께 내보낸다."""
    called = False

    def fake_generate(prompt, *, max_tokens=350, temperature=0.6, json_mode=False):
        nonlocal called
        called = True
        return "오늘은 봄이를 더 많이 떠올리는 날이네요. 그 마음 곁에서 함께할게요."

    result = generate_anniversary_care(
        PET,
        30,
        note="봄이 곁으로 나도 따라가고 싶어요",
        generate=fake_generate,
    )

    assert called is True  # L2 — 케어 메시지는 생성
    assert result["source"] != "safety"
    assert CRISIS_HOTLINE in result["crisis_message"]  # 1393 함께
    assert result["risk_level"] == 2
