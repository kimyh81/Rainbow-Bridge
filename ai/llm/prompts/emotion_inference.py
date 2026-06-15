"""감정 RAG 추론 — 관찰 문장 프롬프트.

`../emotion_inference.py` 가 background 신호(건강 컨디션·교차검증·휴대폰 사용·미션
완료율)로 감정 점수(1~10)와 근거 문장 목록을 **이미 확정**한 뒤, LLM이 있으면
그 근거들을 자연스러운 한 문장으로 다듬습니다(표현만 — 점수·근거는 코드가 정본).

⚠️ 경계 (usage_observation.py 와 동일):
   - **의학적 진단·추측 금지** (우울·불안·질환 등 단정·암시 금지).
   - 점수·등급은 코드가 이미 정했으므로 LLM은 그 등급을 뒤집지 않습니다.
   - 위기(1393)·crisis 자동 트리거 금지 — 여기 문장은 "관찰 요약"까지만.
"""

from __future__ import annotations

from typing import Final

# 점수(1~10) → 등급 라벨. 코드가 정한 정본 — LLM은 이 라벨을 뒤집지 않습니다.
LEVEL_GOOD: Final = "좋음"
LEVEL_NEUTRAL: Final = "보통"
LEVEL_WATCH: Final = "주의"

LEVEL_WORD: Final[dict[str, str]] = {
    LEVEL_GOOD: "비교적 안정적인 편으로 관찰됩니다",
    LEVEL_NEUTRAL: "특별한 변화 없이 보통 수준으로 관찰됩니다",
    LEVEL_WATCH: "평소보다 가라앉은 신호들이 관찰됩니다",
}

SYSTEM_PROMPT: Final[
    str
] = """\
당신은 보호자의 최근 생활 신호(건강 데이터·휴대폰 사용 패턴·미션 수행)를 바탕으로
오늘의 정서 상태를 한 문장으로 요약하는 보조자입니다.

[반드시 지킬 것]
- 의학적 진단·해석 금지 (우울·불안·질환 등 단정·암시 금지).
- 추측 금지 (원인·심리·의도를 짐작하지 마세요).
- 입력으로 주어진 "등급"과 "근거"만 바탕으로, 그 등급을 뒤집지 않는 선에서
  담담한 관찰 한 문장으로 정리하세요.
- 위로·조언·권유는 덧붙이지 마세요(다른 기능에서 따로 처리합니다).

[출력 형식]
반드시 아래 JSON만 출력하세요:
{"sentence": "관찰 문장"}
"""

# LLM 문장 가드 — 진단·추측·위기 암시 표현이 섞이면 규칙 문장으로 폴백.
FORBIDDEN: Final[tuple[str, ...]] = (
    "우울", "불안", "질환", "장애", "진단", "병", "증상",
    "아마", "추정", "보입니다", "보여집니다", "듯", "위험",
    "것같", "지도모", "수도있", "1393", "상담",
)


def build_prompt(level: str, evidence: list[str]) -> str:
    """관찰 문장 생성용 전체 프롬프트(system+user)를 만듭니다.

    Args:
        level: 코드가 정한 등급(``LEVEL_GOOD``/``LEVEL_NEUTRAL``/``LEVEL_WATCH``).
        evidence: 코드가 만든 근거 문장 목록(정본).

    Returns:
        provider.generate(json_mode=True) 에 넘길 프롬프트 문자열.
    """
    bullet = "\n".join(f"- {e}" for e in evidence) or "- (특이 신호 없음)"
    user = (
        f"[등급] {level} — {LEVEL_WORD.get(level, '')}\n"
        f"[근거]\n{bullet}\n\n"
        "[요청] 위 등급을 뒤집지 않는 선에서, 근거를 담담한 관찰 한 문장으로 정리해 "
        "위 JSON 형식으로만 출력하세요."
    )
    return f"{SYSTEM_PROMPT}\n{user}"
