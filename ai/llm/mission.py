"""⑤ 미션 추천 — 로직.

보호자의 감정 점수·경과일에 맞춰 **작은 회복 미션**을 추천합니다. 난이도는 규칙으로
정하고(안전·일관성), 문구는 LLM 으로 개인화하되 실패하면 큐레이션된 규칙 풀로
폴백합니다(graceful). memorial 과 같은 '주입(generate) + 가드 + 폴백' 패턴.

흐름:
    emotion_score → 난이도 결정 → (LLM 생성 시도 → 검증·중복제거)
                  → 부족하면 규칙 풀로 보충/폴백 → count 개 반환

🚫 경계(../CLAUDE.md §0): 반려동물 부활/1인칭·위험한 미션 금지. 규칙 풀과 LLM
가드 양쪽에 적용합니다.
"""

from __future__ import annotations

import json
from typing import Optional, Protocol, Sequence

from ai.rag.retrieve import retrieve as _rag_retrieve
from .prompts import mission as mission_prompt


class GenerateFn(Protocol):
    """provider.generate 와 맞춘 호출 시그니처 (주입용)."""

    def __call__(
        self,
        prompt: str,
        *,
        max_tokens: int = 512,
        temperature: float = 0.7,
        json_mode: bool = False,
    ) -> str: ...


# 생성 파라미터 (잠정).
_MAX_TOKENS: int = 512
_TEMPERATURE: float = 0.8  # 미션은 다양성이 좋아 약간 높게

# 부활/되살림 표현 — 미션에 섞이면 제외(2차 가드).
_FORBIDDEN: tuple[str, ...] = ("부활", "환생", "되살", "다시살아")


# --------------------------------------------------------------------------- #
# 규칙 풀 — LLM 폴백/보충용. 난이도별 (제목, 설명, 카테고리).
# --------------------------------------------------------------------------- #
_RULE_POOL: dict[str, tuple[tuple[str, str, str], ...]] = {
    "gentle": (
        ("물 한 잔 마시기", "천천히 물 한 잔을 마시며 숨을 고르세요.", "rest"),
        ("가슴에 손 얹고 다독이기", "가슴에 손을 얹고 천천히 숨을 쉬며 스스로 다독여보세요.", "rest"),
        ("창가에 앉아 있기", "창가에 앉아 잠시 바깥을 바라보며 숨을 고르세요.", "rest"),
        ("좋아하는 음악 한 곡", "마음이 편해지는 음악을 한 곡 들어보세요.", "rest"),
        (
            "사진 한 장 바라보기",
            "함께한 사진 한 장을 천천히 바라보세요.",
            "remembrance",
        ),
        ("눈 감고 숨 세 번", "눈을 감고 천천히 깊게 숨을 세 번 쉬어보세요.", "rest"),
        ("담요 덮고 쉬기", "따뜻한 담요를 덮고 잠시 몸을 쉬게 해주세요.", "rest"),
        (
            "좋아하는 간식 하나",
            "좋아하는 간식을 천천히 먹으며 잠시 쉬어가세요.",
            "rest",
        ),
        (
            "이름 한 번 불러보기",
            "반려동물의 이름을 조용히 한 번 불러보세요.",
            "remembrance",
        ),
        ("오늘 감정 한 줄", "지금 느끼는 감정을 휴대폰 메모장에 한 줄로만 적어보세요.", "record"),
        ("좋아하는 향 맡기", "향초나 커피처럼 좋아하는 향을 잠시 맡아보세요.", "rest"),
        (
            "부드러운 것 안고 있기",
            "쿠션이나 담요처럼 부드러운 것을 잠시 안고 있어보세요.",
            "rest",
        ),
        (
            "나에게 한마디 건네기",
            "'오늘도 잘 견뎠어'처럼 건네고 싶은 말을 나에게 들려주세요.",
            "rest",
        ),
        (
            "좋아했던 물건 바라보기",
            "아이가 좋아했던 물건 하나를 가만히 바라보세요.",
            "remembrance",
        ),
        (
            "가까운 사람에게 짧은 메시지",
            "연락하고 싶은 사람이 있다면 이모티콘 하나라도 보내보세요.",
            "connection",
        ),
        (
            "대화방 한 번 열어보기",
            "연락하지 않아도 좋아요. 기댈 수 있는 사람의 프로필이나 대화방을 잠시 열어보며 '혼자가 아니다'를 느껴보세요.",
            "connection",
        ),
        ("오늘 마음 한 줄", "오늘 가장 크게 남은 마음을 메모장에 한 줄로 적어보세요.", "record"),
        (
            "따뜻한 물에 손 담그기",
            "따뜻한 물에 잠시 손을 담그며 온기를 느껴보세요.",
            "rest",
        ),
        (
            "좋아하는 사진 한 장 저장",
            "마음에 드는 사진 한 장을 골라 저장해보세요.",
            "remembrance",
        ),
        (
            "짧은 글귀 하나 읽기",
            "마음에 닿는 짧은 글 하나를 천천히 읽어보세요.",
            "rest",
        ),
    ),
    "small": (
        ("집 앞 5분 산책", "날씨가 괜찮으면 집 근처를, 아니면 집 안을 5분만 천천히 걸어보세요.", "activity"),
        ("간단한 집안일 하나", "설거지나 빨래 하나만 가볍게 해보세요.", "activity"),
        ("추억 한 가지 적기", "함께한 기억 하나를 메모장에 짧게 적어보세요.", "record"),
        (
            "물건 하나 정리하기",
            "반려동물의 물건 하나를 천천히 정리해보세요.",
            "remembrance",
        ),
        (
            "안부 한 줄 보내기",
            "편한 사람이 떠오르면 짧게 안부를 전해보세요.",
            "connection",
        ),
        (
            "좋아했던 장소 떠올리기",
            "함께 자주 갔던 곳을 떠올리며 잠시 머물러보세요.",
            "remembrance",
        ),
        (
            "10분 가볍게 스트레칭",
            "몸을 가볍게 풀어주며 일상의 감각을 되찾아보세요.",
            "activity",
        ),
        (
            "오늘 해낸 작은 일 하나",
            "오늘 한 일 중 '그래도 이건 했네' 싶은 것 하나를 떠올려보세요.",
            "rest",
        ),
        ("10분 낮잠 자기", "잠깐 눈을 붙여 10분만 몸을 쉬게 해주세요. 잠이 안 오면 눈만 감고 쉬어도 좋아요.", "rest"),
        ("고마운 것 세 가지", "오늘 고마웠던 것 세 가지를 메모장에 짧게 적어보세요.", "record"),
        (
            "음악 들으며 정리",
            "음악을 들으며 책상 한쪽을 가볍게 정리해보세요.",
            "rest",
        ),
        (
            "오늘 본 좋은 것 적기",
            "오늘 눈에 들어온 좋은 것 하나를 메모장에 적어보세요.",
            "record",
        ),
        (
            "편한 사람과 짧은 통화",
            "편한 사람에게 전화해 5분만 이야기를 나눠보세요.",
            "connection",
        ),
        ("해준 것 하나 적기", "그날의 아이에게 해준 것 하나를 떠올려 메모장에 적어보세요.", "record"),
        (
            "함께 듣던 노래 듣기",
            "아이와 함께 듣던, 또는 떠오르는 노래를 들어보세요.",
            "remembrance",
        ),
        ("오늘 기분 색으로", "지금 기분을 색 하나로 떠올려 메모장에 적어보세요.", "record"),
        ("편한 영상 하나 보기", "마음이 편해지는 영상 하나를 짧게 보세요.", "rest"),
        ("화분에 물 주기", "집에 식물이 있다면 물을 한 번 주어보세요. 없다면 가까운 초록 식물을 잠시 바라봐도 좋아요.", "rest"),
        (
            "가까운 사람에게 사진",
            "아이 사진 한 장을 가까운 사람에게 보내보세요.",
            "connection",
        ),
        (
            "따뜻한 물로 샤워하기",
            "따뜻한 물이 닿는 감각에 집중하며 무거워진 몸과 마음을 잠시 씻어내듯 이완해보세요.",
            "rest",
        ),
        (
            "펫로스 위로 글 읽기",
            "비슷한 이별을 겪은 사람들의 수기나 위로 글을 읽으며, 지금의 슬픔이 당연한 애도임을 함께 느껴보세요.",
            "connection",
        ),
    ),
    "active": (
        ("산책길 다시 걷기", "날씨 좋은 날, 둘이 함께 걷던 길을 천천히 걸어보세요.", "remembrance"),
        ("추억 사진 정리하기", "함께한 사진을 모아 앨범으로 정리해보세요.", "remembrance"),
        ("가까운 곳 다녀오기", "가보고 싶던 가까운 곳에 잠시 들러보세요.", "activity"),
        (
            "작은 화분 하나 들이기",
            "마음에 드는 작은 식물을 하나 들여, 돌보며 일상의 리듬을 찾아보세요.",
            "activity",
        ),
        ("편지 한 통 쓰기", "반려동물에게 전하고 싶은 말을 메모장에 편지처럼 써보세요.", "record"),
        ("새로운 산책 코스", "날씨 좋은 날, 한 번도 안 가본 길을 천천히 걸어보세요.", "activity"),
        ("맛있는 식사 차리기", "스스로를 위해 좋아하는 음식을 차려보세요.", "activity"),
        ("가까운 사람과 만남 잡기", "가까운 사람과 만날 약속을 잡아보세요.", "connection"),
        ("추억 영상 만들기", "함께한 사진들로 짧은 슬라이드를 만들어보세요.", "remembrance"),
        (
            "나에게 위로 편지",
            "힘들 때, 친구를 위로하듯 나에게 짧은 편지를 메모장에 써보세요.",
            "record",
        ),
        ("편한 사람과 식사 약속", "편한 사람과 만나 식사 약속을 잡아보세요.", "connection"),
        (
            "아이 이야기 들려주기",
            "이야기를 들어줄 만한 사람에게 아이와의 추억을 들려주세요.",
            "connection",
        ),
        (
            "가벼운 취미 시작하기",
            "전부터 해보고 싶던 가벼운 취미를 하나 시작해보세요.",
            "activity",
        ),
        (
            "좋았던 하루 떠올리기",
            "아이와 함께한 좋았던 하루를 천천히 떠올려보세요.",
            "remembrance",
        ),
        (
            "기억하는 날 표시하기",
            "아이를 기억하고 싶은 날을 달력에 표시해보세요.",
            "remembrance",
        ),
        (
            "좋아하는 곳에서 사진",
            "기분이 좋아지는 장소에서 사진을 남겨보세요.",
            "activity",
        ),
        (
            "가벼운 운동 15분",
            "스트레칭이나 가벼운 운동으로 15분 몸을 움직여보세요.",
            "activity",
        ),
        (
            "아이에게 쓴 편지 읽기",
            "메모장에 써둔 편지가 있다면 소리 내어 천천히 읽어보세요. 아직 없다면 지금 한 줄부터 써도 좋아요.",
            "remembrance",
        ),
    ),
}


# 건너뛰기(skip) 재추천 시 제외할 "조건부" 미션 제목 — 날씨·자원(구매)·상대방
# 가용성에 의존해, 다시 떠도 같은 이유로 또 못 할 수 있는 미션
# ([[project_mission_active_pick_and_outing_verify]] 설계 조건: 대체 미션은
# "무조건 가능"만). `_rule_missions(..., unconditional_only=True)` 에서 제외됩니다.
_CONDITIONAL_TITLES: frozenset[str] = frozenset(
    {
        # gentle — 집에 담요/향초 등이 없거나, 연락할 사람이 없으면 못 함
        "담요 덮고 쉬기",
        "좋아하는 향 맡기",
        "가까운 사람에게 짧은 메시지",
        # small — 날씨·집안일 거리·상대방 가용성에 의존
        "집 앞 5분 산책",
        "간단한 집안일 하나",
        "안부 한 줄 보내기",
        "편한 사람과 짧은 통화",
        "가까운 사람에게 사진",
        # active — 날씨·외출·구매·상대방 가용성에 의존
        "산책길 다시 걷기",
        "가까운 곳 다녀오기",
        "작은 화분 하나 들이기",
        "새로운 산책 코스",
        "맛있는 식사 차리기",
        "가까운 사람과 만남 잡기",
        "편한 사람과 식사 약속",
        "아이 이야기 들려주기",
        "좋아하는 곳에서 사진",
    }
)


# 난이도 순서(작음 → 큼). 회복 추이로 한 단계 올리고/내릴 때 인덱스로 씁니다.
_DIFFICULTY_ORDER: tuple[str, ...] = ("gentle", "small", "active")


def _difficulty(emotion_score: Optional[int]) -> str:
    """감정 점수 → 난이도. 점수가 없으면 중간(small)."""
    if emotion_score is None:
        return "small"
    if emotion_score <= 3:
        return "gentle"
    if emotion_score <= 6:
        return "small"
    return "active"


def _apply_trend(difficulty: str, recovery_trend: Optional[str]) -> str:
    """최근 회복 추이로 난이도를 한 단계 보정합니다.

    같은 점수라도 "올라오는 중"인지 "내려가는 중"인지로 난이도를 조절합니다
    (차별점: 단일 점수가 아닌 최근 추이 반영).

    - "회복 중"  → 한 단계 올림(gentle→small→active). 조금 더 활동적인 미션.
    - "주의 필요" → 한 단계 내림(active→small→gentle). 더 작고 부담 없는 미션.
    - "유지 중"·"데이터 없음"·None → 그대로.

    띄어쓰기 차이("회복 중"/"회복중")에 견디도록 공백을 제거해 비교합니다.
    """
    if not recovery_trend:
        return difficulty
    key = recovery_trend.replace(" ", "")
    try:
        idx = _DIFFICULTY_ORDER.index(difficulty)
    except ValueError:
        return difficulty
    if key == "회복중":
        idx = min(idx + 1, len(_DIFFICULTY_ORDER) - 1)
    elif key == "주의필요":
        idx = max(idx - 1, 0)
    return _DIFFICULTY_ORDER[idx]


def _apply_sleep(difficulty: str, sleep_quality: Optional[int]) -> str:
    """수면 질(5단계)로 난이도를 한 단계 보정합니다.

    수면은 회복 점수엔 **안 들어가고**(논문 근거는 '연관'까지), '그날 컨디션' 신호로
    추천 미션 난이도만 살짝 조절합니다([[project_sleep_signal_decision]]).
    5단계 입력을 3축약(dead-zone)으로 매핑:

    - 1·2 (나쁨) → 한 단계 내림(더 작고 부담 없는 미션)
    - 3   (보통) → 그대로
    - 4·5 (좋음) → 한 단계 올림(조금 더 활동적인 미션)

    None 이거나 난이도 키가 이상하면 그대로 둡니다(graceful). 저장·표시는 5단계 그대로
    쓰고, 여기(미션 난이도)에서만 3축약합니다.
    """
    if sleep_quality is None:
        return difficulty
    try:
        idx = _DIFFICULTY_ORDER.index(difficulty)
    except ValueError:
        return difficulty
    if sleep_quality <= 2:
        idx = max(idx - 1, 0)
    elif sleep_quality >= 4:
        idx = min(idx + 1, len(_DIFFICULTY_ORDER) - 1)
    return _DIFFICULTY_ORDER[idx]


def _is_safe(mission: dict) -> bool:
    """미션 문구에 금지 표현(부활 등)이 없는지."""
    text = (mission.get("title", "") + mission.get("description", "")).replace(" ", "")
    return not any(bad in text for bad in _FORBIDDEN)


def _rule_missions(
    difficulty: str,
    exclude: set[str],
    count: int,
    *,
    unconditional_only: bool = False,
) -> list[dict]:
    """규칙 풀에서 exclude 를 제외하고 count 개를 뽑습니다.

    연구 권장 카테고리(prompts.mission.DIFFICULTY_CATEGORIES)를 **라운드로빈**으로 돌며
    한 카테고리에 쏠리지 않게 고릅니다 — 같은 난이도라도 회복 단계에 맞는 분류가
    '고루' 노출되도록(발표준비_논문근거.md §감정 상태 × 미션 구조).
    예: gentle 3개 → 기록·추모·자기돌봄 각 1개(rest 도배 방지). 부족분은 나머지로 보충.

    Args:
        unconditional_only: True면 `_CONDITIONAL_TITLES`(날씨·자원·상대방 가용성에
            의존하는 미션)도 추가로 제외합니다 — 건너뛰기(skip) 재추천용
            (`recommend_replacement`).
    """
    prescribed = mission_prompt.DIFFICULTY_CATEGORIES.get(difficulty, ())
    pool = _RULE_POOL[difficulty]
    # 카테고리별 버킷(풀 순서 유지, exclude 제외).
    by_cat: dict[str, list[tuple[str, str, str]]] = {}
    for m in pool:
        if m[0] in exclude:
            continue
        if unconditional_only and m[0] in _CONDITIONAL_TITLES:
            continue
        by_cat.setdefault(m[2], []).append(m)
    # 권장 카테고리를 한 칸씩 번갈아 가며(라운드로빈) 쌓는다 → 분류 다양성 확보.
    ordered: list[tuple[str, str, str]] = []
    depth = 0
    while any(len(by_cat.get(cat, ())) > depth for cat in prescribed):
        for cat in prescribed:
            bucket = by_cat.get(cat, ())
            if depth < len(bucket):
                ordered.append(bucket[depth])
        depth += 1
    # 나머지(비권장 분류)는 뒤에 보충 — count 못 채울 때만 쓰임.
    for cat, bucket in by_cat.items():
        if cat not in prescribed:
            ordered.extend(bucket)
    out: list[dict] = []
    for title, desc, category in ordered:
        if title in exclude:
            continue
        out.append(
            {
                "title": title,
                "description": desc,
                "category": category,
                "rationale": mission_prompt.CATEGORY_RATIONALE.get(category, ""),
            }
        )
        if len(out) >= count:
            break
    return out


def _parse_llm(raw: str) -> list[dict]:
    """LLM JSON 출력을 미션 리스트로 파싱(형식이 깨지면 빈 리스트)."""
    data = json.loads(raw)
    items = data.get("missions") if isinstance(data, dict) else data
    if not isinstance(items, list):
        return []
    result: list[dict] = []
    for it in items:
        if not isinstance(it, dict):
            continue
        title = str(it.get("title", "")).strip()
        if not title:
            continue
        category = it.get("category")
        cat = category if category in mission_prompt.CATEGORIES else "activity"
        result.append(
            {
                "title": title,
                "description": str(it.get("description", "")).strip(),
                "category": cat,
                # 근거는 LLM 출력이 아니라 카테고리 기준으로 부착(=일관성·환각 방지).
                "rationale": mission_prompt.CATEGORY_RATIONALE.get(cat, ""),
            }
        )
    return result


# --- 미션 구성(난이도 조합) — 06-15, 회복점수 레벨별 ---------------------------- #
# [[project_recovery_score_axes_redesign_260614]] 확정: 그날 미션은 "단일 난이도
# count개 반복"이 아니라, 레벨/점수에 따른 **난이도 조합**이다.
#   - L2~3: G×3 (고정)
#   - L1:   G×2+Sm×1 또는 G×1+Sm×2 (어느 쪽인지는 감정점수로 결정)
#   - L0:   0~45점=L1과 동일(3개) / 45~100점=A×1(1개로 축소)
_L0_ACTIVE_THRESHOLD = 45


def _l1_composition(emotion_score: Optional[int]) -> tuple[str, ...]:
    """L1(및 L0의 0~45 구간) 미션 구성 — G×2+Sm×1 또는 G×1+Sm×2.

    감정점수가 낮을(힘들)수록 gentle 비중을 높인다(G×2+Sm×1).
    """
    if emotion_score is not None and emotion_score <= 3:
        return ("gentle", "gentle", "small")
    return ("gentle", "small", "small")


def mission_composition(
    level: Optional[str],
    score: Optional[int] = None,
    emotion_score: Optional[int] = None,
) -> Optional[tuple[str, ...]]:
    """레벨(L2~3/L1/L0)·점수(L0 한정)로 오늘 미션 난이도 조합을 결정합니다.

    Args:
        level: ``"L2~3"`` | ``"L1"`` | ``"L0"``. None 이면 None 반환 — `recommend()`
            는 이때 기존 단일 난이도 동작(하위호환)으로 처리합니다.
        score: recovery_score(0~100). **L0에서만** `_L0_ACTIVE_THRESHOLD`(45)점
            기준으로 1개(active)/3개를 가른다(레벨과 점수는 독립 축 — L2~3/L1에는
            cap·점수 분기 없음).
        emotion_score: L1(또는 L0의 45점 미만 구간)에서 G×2+Sm×1 vs G×1+Sm×2
            선택 기준.

    Returns:
        난이도 튜플(예: ``("gentle", "gentle", "small")``). level이 인식되지 않으면 None.
    """
    if level == "L2~3":
        return ("gentle", "gentle", "gentle")
    if level == "L1":
        return _l1_composition(emotion_score)
    if level == "L0":
        if score is not None and score >= _L0_ACTIVE_THRESHOLD:
            return ("active",)
        return _l1_composition(emotion_score)
    return None


def _recommend_by_composition(
    composition: Sequence[str], history: Optional[list[str]]
) -> list[dict]:
    """난이도 조합대로 규칙 풀에서 1개씩 뽑아 합칩니다.

    레벨 기반 조합은 슬롯마다 난이도가 달라 LLM 프롬프트(단일 난이도 가정)와
    맞지 않으므로, 규칙 풀에서 결정적으로 뽑는다(`_rule_missions`). 각 결과에
    그 슬롯의 ``difficulty`` 를 태그한다.
    """
    used: set[str] = set(history or [])
    out: list[dict] = []
    for difficulty in composition:
        for m in _rule_missions(difficulty, used, 1):
            m["difficulty"] = difficulty
            used.add(m["title"])
            out.append(m)
    return out


def recommend(
    emotion_score: Optional[int],
    day_since: Optional[int] = None,
    history: Optional[list[str]] = None,
    *,
    recovery_trend: Optional[str] = None,
    sleep_quality: Optional[int] = None,
    generate: Optional[GenerateFn] = None,
    count: int = 3,
    level: Optional[str] = None,
    recovery_score: Optional[int] = None,
) -> list[dict]:
    """회복 미션을 추천합니다.

    Args:
        emotion_score: 보호자 감정 점수(1~10, 낮을수록 힘듦). None 이면 중간 난이도.
        day_since: 반려동물을 떠나보낸 뒤 경과일(선택).
        history: 최근 추천/완료한 미션 제목(중복 회피).
        recovery_trend: 최근 7회 추이(백엔드 get_recovery 의 trend: "회복 중"·"유지 중"
            ·"주의 필요"·"데이터 없음"). 점수 기반 난이도를 한 단계 보정합니다.
            없으면 점수만 사용(graceful).
        sleep_quality: 그날 수면 질(5단계, 1~5). 난이도를 3축약으로 보정(1·2↓ / 3 유지
            / 4·5↑). 회복 점수엔 안 들어감 — 미션 강도 조절용. None 이면 미적용.
        generate: LLM 호출 함수(provider.generate). None 이면 규칙 기반만 사용.
        count: 추천 개수. ``level`` 이 주어지면 무시되고 `mission_composition()`
            의 길이(보통 3, L0 45+ 는 1)를 따릅니다.
        level: ``"L2~3"`` | ``"L1"`` | ``"L0"`` (회복점수 risk_level). 주어지면
            난이도 **조합**(`mission_composition`)으로 추천하고, 규칙 풀만 사용
            (결정적, LLM 미사용). None 이면 기존 단일 난이도 동작(하위호환).
        recovery_score: 0~100 누적 점수. ``level="L0"`` 일 때만 45점 기준 분기에 사용.

    Returns:
        ``[{title, description, category, rationale, difficulty}, ...]``.
        ``level`` 미지정 시 최대 count개(기존 동작), 지정 시 조합 길이만큼
        (보통 3개, L0 45+ 는 1개). ``rationale`` 은 카테고리별 회복 근거 한 줄
        (prompts.mission.CATEGORY_RATIONALE).
    """
    composition = mission_composition(level, recovery_score, emotion_score)
    if composition is not None:
        return _recommend_by_composition(composition, history)
    difficulty = _apply_sleep(
        _apply_trend(_difficulty(emotion_score), recovery_trend), sleep_quality
    )
    recent: set[str] = set(history or [])
    score = emotion_score if emotion_score is not None else 5

    # RAG 검색 — 회복 미션 예시 검색. 난이도까지 필터해 맥락에 맞는 예시만 가져옴
    # (키 2개라 $and 필요). 실패 시 graceful fallback.
    rag_hits = None
    try:
        query = mission_prompt.DIFFICULTY_GUIDE.get(difficulty, "회복 미션")
        rag_hits = _rag_retrieve(
            query,
            k=3,
            where={"$and": [{"category": "mission"}, {"difficulty": difficulty}]},
        )
    except Exception:
        rag_hits = None

    missions: list[dict] = []

    # LLM 개인화 시도 — 실패/이상 출력이면 조용히 폴백.
    if generate is not None:
        try:
            prompt = mission_prompt.build_prompt(
                emotion_score=score,
                difficulty=difficulty,
                day_since=day_since,
                recent_titles=sorted(recent),
                count=count,
                rag_hits=rag_hits,
                recovery_trend=recovery_trend,
            )
            raw = generate(
                prompt,
                max_tokens=_MAX_TOKENS,
                temperature=_TEMPERATURE,
                json_mode=True,
            )
            for m in _parse_llm(raw):
                if m["title"] not in recent and _is_safe(m):
                    missions.append(m)
        except Exception:  # noqa: BLE001 — 추론 실패는 폴백으로 흡수(graceful)
            missions = []

    # 부족분은 규칙 풀로 보충(=LLM 미사용 시 전량 규칙 폴백).
    if len(missions) < count:
        used = recent | {m["title"] for m in missions}
        missions += _rule_missions(difficulty, used, count - len(missions))

    for m in missions:
        m.setdefault("difficulty", difficulty)

    return missions[:count]


def recommend_replacement(
    difficulty: str, history: Optional[list[str]] = None
) -> Optional[dict]:
    """건너뛴 미션의 대체 미션 1개를 추천합니다(건너뛰기 1회 허용, 06-13 확정).

    날씨·자원(구매)·상대방 가용성에 의존하는 "조건부" 미션(`_CONDITIONAL_TITLES`)은
    제외하고, 같은 난이도의 "무조건 가능한" 풀에서만 뽑습니다 — 대체 미션도
    조건부면 같은 이유로 또 못 할 수 있어 같은 문제가 반복되기 때문입니다
    ([[project_mission_active_pick_and_outing_verify]] 설계 조건).

    Args:
        difficulty: 건너뛴 미션의 난이도(gentle·small·active). 대체 미션도 같은
            난이도를 유지합니다(레벨별 미션 구성 비중을 깨지 않도록).
        history: 최근 추천/완료(+건너뛴) 미션 제목(중복 회피).

    Returns:
        ``{title, description, category, rationale, difficulty}`` 1개.
        해당 난이도의 무조건 가능 풀이 모두 소진되면(이론상 거의 없음) None.
    """
    used = set(history or [])
    out = _rule_missions(difficulty, used, 1, unconditional_only=True)
    if not out:
        return None
    out[0]["difficulty"] = difficulty
    return out[0]
