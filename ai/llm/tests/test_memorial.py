"""③ 추모 메시지 로직·프롬프트 테스트.

LLM 없이도 검증 가능한 것만 다룹니다(실제 모델 품질은 provider 확정 후 단계):
  1. 프롬프트 조립 — 입력값이 정확히 채워지고 가드 문구가 박혀 있는가.
  2. 흐름 — 가짜 generate 를 주입해 generate_message 의 단계가 맞는가.
  3. 안전 — 위기 입력은 메시지보다 1393 안내가 우선인가.
  4. 가드 — 부활/1인칭 출력은 차단되는가.
"""

from __future__ import annotations

import pytest

from ..memorial import GuardrailViolation, generate_message
from ..prompts import memorial as memorial_prompt
from ..safety import CRISIS_HOTLINE

PET = {
    "name": "봄이",
    "species": "강아지",
    "period": "12년",
    "memories": ["아침마다 현관에서 기다림", "노란 공놀이"],
}


# --- 1. 프롬프트 조립 -------------------------------------------------------- #


def test_prompt_fills_inputs():
    prompt = memorial_prompt.build_user_prompt(
        name="봄이", species="강아지", period="12년", score=3, note="산책을 좋아했어요"
    )
    assert "봄이" in prompt
    assert "강아지" in prompt
    assert "12년" in prompt
    assert "3/10" in prompt
    assert "산책을 좋아했어요" in prompt


def test_prompt_includes_memories_when_given():
    prompt = memorial_prompt.build_user_prompt(
        name="봄이", species="강아지", period="12년", score=5, memories=["노란 공놀이"]
    )
    assert "노란 공놀이" in prompt


def test_prompt_omits_memory_block_when_empty():
    prompt = memorial_prompt.build_user_prompt(
        name="봄이", species="강아지", period="12년", score=5, memories=[]
    )
    assert "함께한 추억" not in prompt


def test_unknown_tone_falls_back_to_default():
    prompt = memorial_prompt.build_user_prompt(
        name="봄이", species="강아지", period="12년", score=5, tone="존재하지않는톤"
    )
    assert memorial_prompt.TONE_GUIDE[memorial_prompt.DEFAULT_TONE] in prompt


def test_system_prompt_has_ethics_guardrails():
    """🚨 시스템 프롬프트에 1인칭·부활 금지가 실제로 박혀 있어야 한다."""
    system = memorial_prompt.SYSTEM_PROMPT
    assert "1인칭" in system
    assert "살아나" in system or "돌아온다" in system


def test_build_messages_has_system_and_user():
    messages = memorial_prompt.build_messages(
        name="봄이", species="강아지", period="12년", score=5
    )
    assert [m["role"] for m in messages] == ["system", "user"]


# --- 2. 흐름 (가짜 generate 주입) ------------------------------------------- #


def test_generate_message_uses_injected_generate():
    """generate_message 가 주입된 generate 의 출력을 그대로 감싸는지."""
    fake_output = "봄이와 함께한 아침 산책의 온기가 당신 곁에 오래 머물기를 바랍니다."

    def fake_generate(prompt, *, max_tokens=400, temperature=0.7, json_mode=False):
        assert "봄이" in prompt  # 프롬프트가 실제로 전달됐는지
        return fake_output

    result = generate_message(
        PET, {"emotion_score": 3, "note": "너무 보고 싶어요"}, generate=fake_generate
    )
    assert result["content"] == fake_output
    assert result["source"] == "local"
    assert result["tone"] == memorial_prompt.DEFAULT_TONE


# --- 2.5 배선: pet 의 버킷리스트·보호자 호칭이 프롬프트로 흘러가는지 ---------- #


def test_generate_message_injects_bucket_list_and_caller():
    """pet 의 bucket_list·caller_name 이 실제 프롬프트에 박혀야 한다(C 배선)."""
    captured = {}

    def fake_generate(prompt, *, max_tokens=400, temperature=0.7, json_mode=False):
        captured["prompt"] = prompt
        return "봄이와 함께한 시간이 당신을 따뜻하게 지켜줄 거예요."

    pet = {
        "name": "봄이",
        "species": "강아지",
        "period": "12년",
        "memories": ["노란 공놀이"],
        "bucket_list": ["같이 해 뜨는 거 보기", "바다 보여주기"],
        "caller_name": "엄마",
    }
    generate_message(pet, {"emotion_score": 3, "note": "보고 싶어요"}, generate=fake_generate)
    prompt = captured["prompt"]
    assert "같이 해 뜨는 거 보기" in prompt
    assert "바다 보여주기" in prompt
    assert "버킷리스트" in prompt
    assert "엄마" in prompt


def test_guardian_nickname_greets_in_third_person():
    """별명이 있으면 3인칭 글 첫머리 '○○님,' 호명 지시가 프롬프트에 들어간다."""
    captured = {}

    def fake_generate(prompt, *, max_tokens=400, temperature=0.7, json_mode=False):
        captured["prompt"] = prompt
        return "하늘님, 봄이는 알고 있었습니다. 봄이는 충분히 사랑받았습니다."

    pet = {"name": "봄이", "species": "강아지", "period": "12년", "caller_name": "엄마"}
    generate_message(
        pet, {"emotion_score": 5}, generate=fake_generate, guardian_nickname="하늘"
    )
    assert "하늘님," in captured["prompt"]


def test_guardian_nickname_used_throughout_third_person():
    """별명이 있으면 본문 묘사도 보호자 호칭(엄마) 대신 별명('○○님')으로 통일한다."""
    captured = {}

    def fake_generate(prompt, *, max_tokens=400, temperature=0.7, json_mode=False):
        captured["prompt"] = prompt
        return "하늘님, 봄이는 알고 있었습니다."

    pet = {"name": "봄이", "species": "강아지", "period": "12년", "caller_name": "엄마"}
    generate_message(
        pet, {"emotion_score": 5}, generate=fake_generate, guardian_nickname="하늘"
    )
    prompt = captured["prompt"]
    # 본문 묘사 지시("…이 해준 일을")가 별명으로 채워지고(받침 맞춰 조사 교정),
    # 엄마(caller)로 묘사하지 않는다.
    assert "하늘님이 해준 일을" in prompt
    assert "엄마가 해준 일을" not in prompt
    # 끝까지 같은 별명으로 부르라는 지시가 들어간다.
    assert "다른 호칭으로 바꾸지 마세요" in prompt


def test_guardian_nickname_ignored_in_first_person():
    """1인칭 모드에선 별명 호명을 넣지 않는다(caller_name 으로 부름)."""
    captured = {}

    def fake_generate(prompt, *, max_tokens=400, temperature=0.7, json_mode=False):
        captured["prompt"] = prompt
        return "엄마, 나 봄이야. 강아지별로 이사 가. 조금만 울고 밥 먹어."

    pet = {"name": "봄이", "species": "강아지", "period": "12년", "caller_name": "엄마"}
    generate_message(
        pet,
        {"emotion_score": 8},
        generate=fake_generate,
        guardian_nickname="하늘",
        first_person=True,
    )
    assert "하늘님" not in captured["prompt"]


def test_generate_message_works_without_bucket_list():
    """버킷리스트·호칭이 없어도(기존 호출) 정상 동작한다(기본값 '보호자')."""
    def fake_generate(prompt, *, max_tokens=400, temperature=0.7, json_mode=False):
        return "봄이와 나눈 시간이 당신 곁에 머물기를 바랍니다."

    result = generate_message(
        PET, {"emotion_score": 4, "note": "보고 싶어요"}, generate=fake_generate
    )
    assert result["source"] == "local"


# --- 3. 안전: 위기 입력은 1393 우선 ----------------------------------------- #


def test_l3_crisis_blocks_generation():
    """L3(긴급: 구체적 수단·계획)이면 생성을 전면 중단하고 1393 만 내보낸다."""
    called = False

    def fake_generate(prompt, *, max_tokens=400, temperature=0.7, json_mode=False):
        nonlocal called
        called = True
        return "이 문장은 나오면 안 됩니다."

    result = generate_message(
        PET,
        {"emotion_score": 1, "note": "유서를 쓰고 목을 매려고 해요"},
        generate=fake_generate,
    )
    assert called is False  # L3 — 생성 자체를 건너뜀
    assert result["source"] == "safety"
    assert CRISIS_HOTLINE in result["crisis_message"]
    assert CRISIS_HOTLINE in result["content"]


def test_l2_crisis_generates_with_hotline():
    """L2(경고: 사망 욕구)면 메시지는 생성하되 1393 안내를 함께 내보낸다."""
    called = False

    def fake_generate(prompt, *, max_tokens=400, temperature=0.7, json_mode=False):
        nonlocal called
        called = True
        return "봄이는 늘 곁에서 환하게 웃어주었죠. 그 따뜻함은 잊지 않을게요."

    result = generate_message(
        PET,
        {"emotion_score": 1, "note": "봄이 곁으로 나도 따라가고 싶어요"},
        generate=fake_generate,
    )
    assert called is True  # L2 — 생성은 진행
    assert result["source"] != "safety"
    assert CRISIS_HOTLINE in result["crisis_message"]  # 1393 함께 표시
    assert result["risk_level"] == 2


# --- 4. 가드: 부활/1인칭 출력 차단 ------------------------------------------ #


def test_resurrection_output_is_blocked():
    def bad_generate(prompt, *, max_tokens=400, temperature=0.7, json_mode=False):
        return "걱정 마세요, 봄이는 곧 다시 살아서 돌아올 거예요."

    with pytest.raises(GuardrailViolation):
        generate_message(
            PET, {"emotion_score": 5, "note": "보고 싶어요"}, generate=bad_generate
        )


def test_guard_retries_then_succeeds():
    """첫 출력이 위반이면 재생성, 다음이 정상이면 통과."""
    outputs = iter(
        [
            "봄이가 부활해서 돌아온다.",  # 위반
            "봄이와 나눈 시간이 당신을 따뜻하게 지켜줄 거예요.",  # 정상
        ]
    )

    def flaky_generate(prompt, *, max_tokens=400, temperature=0.7, json_mode=False):
        return next(outputs)

    result = generate_message(
        PET, {"emotion_score": 4, "note": "보고 싶어요"}, generate=flaky_generate
    )
    assert "부활" not in result["content"].replace(" ", "")


# --- 5. 1인칭 편지 모드 (first_person=True) ---------------------------------- #


def test_first_person_prompt_uses_different_template():
    """first_person=True 이면 1인칭 요청 문구가 담긴 템플릿을 사용해야 한다."""
    prompt_default = memorial_prompt.build_user_prompt(
        name="봄이", species="강아지", period="12년", score=5
    )
    prompt_fp = memorial_prompt.build_user_prompt(
        name="봄이", species="강아지", period="12년", score=5, first_person=True
    )
    assert prompt_default != prompt_fp
    assert "1인칭" in prompt_fp or "꿈 속" in prompt_fp


def test_first_person_system_prompt_allows_first_person():
    """SYSTEM_PROMPT_FIRST_PERSON 은 1인칭 허용, 부활 단정은 여전히 금지."""
    sp = memorial_prompt.SYSTEM_PROMPT_FIRST_PERSON
    assert "1인칭" in sp or "나는" in sp  # 1인칭 허용 안내 있어야 함
    assert "부활" in sp or "살아 돌아" in sp  # 부활 금지 안내 있어야 함


def test_build_messages_first_person_uses_first_person_system_prompt():
    messages = memorial_prompt.build_messages(
        name="봄이", species="강아지", period="12년", score=5, first_person=True
    )
    assert messages[0]["content"] == memorial_prompt.SYSTEM_PROMPT_FIRST_PERSON
    assert messages[1]["role"] == "user"


def test_build_messages_default_uses_default_system_prompt():
    messages = memorial_prompt.build_messages(
        name="봄이", species="강아지", period="12년", score=5
    )
    assert messages[0]["content"] == memorial_prompt.SYSTEM_PROMPT


def test_first_person_output_not_blocked():
    """first_person=True 이면 반려동물 1인칭 출력을 차단하지 않는다."""
    fp_output = "나는 봄이야. 같이 산책하던 아침이 나도 참 좋았어. 고마워, 엄마."

    def fake_generate(prompt, *, max_tokens=400, temperature=0.7, json_mode=False):
        assert "꿈 속" in prompt or "1인칭" in prompt  # 1인칭 모드 프롬프트 전달 확인
        return fp_output

    result = generate_message(
        PET, {"emotion_score": 5, "note": "한번만 말해줬으면"}, generate=fake_generate,
        first_person=True,
    )
    assert result["content"] == fp_output
    assert result.get("first_person") is True


def test_first_person_result_includes_flag():
    """first_person=True 로 생성하면 반환 dict 에 first_person: True 가 포함된다."""
    def fake_generate(prompt, *, max_tokens=400, temperature=0.7, json_mode=False):
        return "나는 봄이야. 항상 곁에 있었어."

    result = generate_message(
        PET, {"emotion_score": 6}, generate=fake_generate, first_person=True
    )
    assert result.get("first_person") is True


def test_default_mode_still_blocks_first_person_output():
    """first_person=False(기본)이면 1인칭 출력은 여전히 차단된다."""
    def bad_generate(prompt, *, max_tokens=400, temperature=0.7, json_mode=False):
        return "나는 봄이야. 잘 있어."

    with pytest.raises(GuardrailViolation):
        generate_message(PET, {"emotion_score": 5}, generate=bad_generate)


def test_resurrection_still_blocked_in_first_person_mode():
    """first_person=True 여도 부활/환생 단정 표현은 차단된다."""
    def bad_generate(prompt, *, max_tokens=400, temperature=0.7, json_mode=False):
        return "나는 봄이야. 다시 살아서 돌아올게."

    with pytest.raises(GuardrailViolation):
        generate_message(
            PET, {"emotion_score": 5}, generate=bad_generate, first_person=True
        )


def test_l3_crisis_blocks_first_person():
    """L3(긴급)이면 first_person=True 여도 생성 전면 중단, 1393 만 내보낸다."""
    called = False

    def fake_generate(prompt, *, max_tokens=400, temperature=0.7, json_mode=False):
        nonlocal called
        called = True
        return "나는 봄이야."

    result = generate_message(
        PET,
        {"emotion_score": 1, "note": "유서를 쓰고 목을 매려고 해요"},
        generate=fake_generate,
        first_person=True,
    )
    assert called is False  # L3 — 생성 자체 차단
    assert CRISIS_HOTLINE in result["content"]


def test_l2_crisis_forces_third_person():
    """L2(경고)면 first_person=True 여도 1인칭 편지로 승격하지 않고(3인칭) 1393 을 함께 낸다."""
    called = False

    def fake_generate(prompt, *, max_tokens=400, temperature=0.7, json_mode=False):
        nonlocal called
        called = True
        return "봄이는 늘 곁에서 환하게 웃어주었죠. 그 따뜻함은 잊지 않을게요."

    result = generate_message(
        PET,
        {"emotion_score": 1, "note": "봄이 곁으로 나도 따라가고 싶어요"},
        generate=fake_generate,
        first_person=True,
    )
    assert called is True  # L2 — 생성은 진행
    assert result.get("first_person") is not True  # 1인칭 편지로 승격 안 됨(3인칭)
    assert CRISIS_HOTLINE in result["crisis_message"]  # 1393 함께
    assert result["risk_level"] == 2


# --- 5. graceful: LLM 인프라 실패(LLMError) → 안내문 대체 --------------------- #


def test_llm_unavailable_returns_notice():
    """전 키·모델 소진(LLMError) 시, 가짜 추모글이 아니라 안내문(source=unavailable)."""
    from ..provider import LLM_UNAVAILABLE_NOTICE, LLMError

    def failing_generate(prompt, *, max_tokens=400, temperature=0.7, json_mode=False):
        raise LLMError("모든 키·모델 소진")

    result = generate_message(
        PET, {"emotion_score": 5, "note": "봄이가 보고 싶어요"}, generate=failing_generate
    )
    assert result["source"] == "unavailable"
    assert result["content"] == LLM_UNAVAILABLE_NOTICE
