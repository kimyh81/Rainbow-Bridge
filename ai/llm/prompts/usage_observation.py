"""⑧-확장: 휴대폰 사용 지표 → '관찰 문장' — 프롬프트 템플릿.

세종 PM 수집기(1단계)가 만든 **요약 지표**(지표별 `today`/`avg7`)를 받아,
"최근 일주일 평균 대비 ○○이 증가/감소했습니다" 같은 **사실 관찰 문장**(2단계)만
만들기 위한 프롬프트입니다. 로직은 ../usage_observation.py, 이 파일은 프롬프트만
분리·버전 관리합니다.

⚠️ 경계 (../../evaluation/phone_usage.py 의 advisory 원칙과 동일):
   - **의학적 진단·추측 금지.** today vs avg7 의 *관찰된 변화*만 말합니다.
   - 위기(1393)·crisis 자동 트리거 금지 — 여기 문장은 "관찰" 까지만.
   - 방향(증가/감소/유지)은 코드가 숫자로 정합니다. 프롬프트는 **문장 표현만** 담당.
"""

from __future__ import annotations

from typing import Final

# 지표 키 → 한국어 라벨(문장 주어). 모르는 키는 키 그대로 노출.
# 1단계 수집기가 새 지표를 추가하면 여기 한 줄 추가하세요(세종 PM 협의).
#
# 세종 PM 수집기는 비식별화로 **카테고리 4종**만 보냅니다(raw 패키지명 X):
#   ENTERTAINMENT / SOCIAL / EDUCATION / FINANCE.
# 어댑터(../usage_observation.summarize_category_logs)가 이를 `<소문자>_usage` 키로
# 바꾸고, 전 카테고리 새벽 사용 합을 `night_usage` 로 모읍니다.
DEFAULT_LABELS: Final[dict[str, str]] = {
    "night_usage": "새벽 활동",
    "entertainment_usage": "엔터테인먼트 앱 사용",
    "social_usage": "SNS 사용",
    "education_usage": "교육 관련 앱 사용",
    "finance_usage": "금융 앱 사용",
    "screen_time": "전체 사용 시간",
    # (참고용 — 더 세분화된 카테고리가 생기면 추가)
    "video_usage": "동영상 시청",
    "game_usage": "게임 사용",
    "communication_usage": "메신저·통화",
    "outdoor_usage": "외출·이동 앱 사용",
}


SYSTEM_PROMPT: Final[
    str
] = """\
당신은 사용자 행동 데이터를 분석하는 보조자입니다.
주어진 지표의 '최근 값(today)' 과 '7일 평균(avg7)' 을 비교해, 관찰된 변화만
담담하게 한 문장으로 서술합니다.

[반드시 지킬 것]
- 의학적 진단·해석 금지 (우울·불안·질환 등 단정·암시 금지).
- 추측 금지 (원인·심리·의도를 짐작하지 마세요).
- 관찰된 패턴만 설명 (숫자가 보여주는 증가/감소/유지 사실만).
- 차분한 평서체 한 문장. 위로·조언·권유를 덧붙이지 마세요.

[출력 형식]
반드시 아래 JSON 만 출력하세요. 입력으로 준 지표 key 마다 한 문장씩:
{"observations": [{"key": "<지표 key>", "sentence": "관찰 문장"}]}
"""


# 방향(코드가 정함) → 프롬프트에 주는 한국어 지시어. LLM 은 이 방향을 따릅니다.
DIRECTION_WORD: Final[dict[str, str]] = {
    "증가": "증가했다",
    "감소": "감소했다",
    "유지": "비슷한 수준을 유지했다",
}


def build_prompt(findings: list[dict]) -> str:
    """관찰 문장 생성용 전체 프롬프트(system+user)를 만듭니다.

    Args:
        findings: ../usage_observation.py 가 숫자로 계산한 지표별 결과.
            각 항목: ``{key, label, today, avg7, direction}``. ``direction`` 은
            증가/감소/유지 중 하나로 **이미 확정**된 정본입니다.

    Returns:
        provider.generate(json_mode=True) 에 넘길 프롬프트 문자열.
    """
    lines = []
    for f in findings:
        word = DIRECTION_WORD.get(f["direction"], "변화를 관찰했다")
        lines.append(
            f'- key="{f["key"]}", 지표="{f["label"]}", '
            f"최근={f['today']}분, 7일평균={f['avg7']}분 → 방향: {word}"
        )
    body = "\n".join(lines)
    user = (
        "[지표 — 아래 방향(증가/감소/유지)을 그대로 따라 문장을 쓰세요]\n"
        f"{body}\n\n"
        "[요청]\n"
        "각 key 마다 관찰 문장 하나씩, 위 JSON 형식으로만 출력하세요."
    )
    return f"{SYSTEM_PROMPT}\n{user}"
