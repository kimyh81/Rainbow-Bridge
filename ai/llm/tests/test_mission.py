"""⑤ 미션 추천 테스트 — LLM 없이 규칙·폴백·주입 경로를 검증.

  1. 규칙 기반(LLM 미주입) — 난이도 매핑·개수·중복 회피·구조
  2. LLM 주입 — 정상 JSON 사용 / 깨진 출력·실패 시 폴백
  3. 가드 — 부활 표현 미션 제외
"""

from __future__ import annotations

import json

from .. import mission as mission_mod
from ..mission import recommend
from ..prompts import mission as mission_prompt


# --- 1. 규칙 기반 (generate 미주입) ----------------------------------------- #


def test_rule_based_returns_count():
    result = recommend(emotion_score=2, count=3)
    assert len(result) == 3
    for m in result:
        assert set(m) == {"title", "description", "category", "rationale", "difficulty"}
        assert m["category"] in mission_prompt.CATEGORIES
        # 근거는 카테고리별 회복 근거와 정확히 일치(코드 부착).
        assert m["rationale"] == mission_prompt.CATEGORY_RATIONALE[m["category"]]


def test_low_score_gives_gentle_missions():
    """감정 점수가 낮으면(무기력) gentle 풀에서 나온다."""
    result = recommend(emotion_score=1, count=5)
    titles = {m["title"] for m in result}
    assert "물 한 잔 마시기" in titles or "창문 열고 바람 쐬기" in titles


def test_high_score_gives_active_missions():
    result = recommend(emotion_score=9, count=5)
    titles = {m["title"] for m in result}
    assert "친구와 짧은 통화" in titles or "가까운 곳 다녀오기" in titles


def test_none_score_defaults_to_small():
    result = recommend(emotion_score=None, count=3)
    assert len(result) == 3


# --- 1-b. 논문 재설정: 난이도 × 권장 카테고리 정합 -------------------------- #


def test_gentle_surfaces_diverse_prescribed_categories():
    """재설정: gentle 은 rest 도배가 아니라 기록·추모·자기돌봄이 '고루' 나온다(라운드로빈)."""
    result = recommend(emotion_score=1, count=3)
    cats = [m["category"] for m in result]
    prescribed = set(mission_prompt.DIFFICULTY_CATEGORIES["gentle"])
    assert all(c in prescribed for c in cats)
    assert len(set(cats)) >= 2  # 한 분류 도배 방지(이전 버그: rest 3개)
    assert "record" in cats or "remembrance" in cats  # 글쓰기/추모 최소 1개


def test_small_surfaces_prescribed_categories():
    """재설정: small 은 행동활성화·사회적지지(activity·connection)가 먼저 노출된다."""
    result = recommend(emotion_score=5, count=5)
    prescribed = set(mission_prompt.DIFFICULTY_CATEGORIES["small"])
    assert all(m["category"] in prescribed for m in result)


def test_prompt_includes_category_hint():
    """LLM 프롬프트에 난이도별 권장 분류가 명시된다(텍스트 권유 → 분류 제약)."""
    prompt = mission_prompt.build_prompt(emotion_score=2, difficulty="gentle", count=3)
    assert "권장 분류" in prompt
    assert "record" in prompt and "remembrance" in prompt


def test_history_avoided():
    """history 에 있는 미션은 추천에서 제외된다."""
    first = recommend(emotion_score=2, count=2)
    avoid = [first[0]["title"]]
    again = recommend(emotion_score=2, history=avoid, count=2)
    assert avoid[0] not in {m["title"] for m in again}


# --- 2. LLM 주입 ------------------------------------------------------------ #


def _fake_llm(missions):
    payload = json.dumps({"missions": missions}, ensure_ascii=False)

    def gen(prompt, *, max_tokens=512, temperature=0.8, json_mode=False):
        assert json_mode is True  # 미션은 JSON 강제
        return payload

    return gen


def test_llm_output_used_when_valid():
    fake = _fake_llm(
        [
            {
                "title": "편지 한 줄 쓰기",
                "description": "짧게 적어보세요.",
                "category": "record",
            },
            {
                "title": "창밖 보기",
                "description": "잠시 바깥을 보세요.",
                "category": "rest",
            },
            {"title": "차 한 잔", "description": "따뜻하게.", "category": "rest"},
        ]
    )
    result = recommend(emotion_score=5, generate=fake, count=3)
    assert {m["title"] for m in result} == {"편지 한 줄 쓰기", "창밖 보기", "차 한 잔"}


def test_rationale_attached_to_llm_missions():
    """LLM 이 만든 미션에도 카테고리 기준 근거가 붙는다(환각 아닌 큐레이션 근거)."""
    fake = _fake_llm(
        [
            {
                "title": "편지 한 줄 쓰기",
                "description": "짧게 적어보세요.",
                "category": "record",
            }
        ]
    )
    result = recommend(emotion_score=5, generate=fake, count=1)
    assert result[0]["rationale"] == mission_prompt.CATEGORY_RATIONALE["record"]


def test_llm_broken_output_falls_back_to_rule():
    def bad_gen(prompt, *, max_tokens=512, temperature=0.8, json_mode=False):
        return "이건 JSON 이 아닙니다"

    result = recommend(emotion_score=2, generate=bad_gen, count=3)
    assert len(result) == 3  # 폴백으로 채워짐


def test_llm_failure_falls_back_to_rule():
    def boom(prompt, *, max_tokens=512, temperature=0.8, json_mode=False):
        raise RuntimeError("LLM 다운")

    result = recommend(emotion_score=2, generate=boom, count=3)
    assert len(result) == 3


def test_llm_short_output_topped_up_by_rule():
    """LLM 이 1개만 주면 나머지는 규칙 풀로 보충해 count 를 채운다."""
    fake = _fake_llm(
        [{"title": "딱 하나", "description": "유일한 미션.", "category": "rest"}]
    )
    result = recommend(emotion_score=2, generate=fake, count=3)
    assert len(result) == 3
    assert result[0]["title"] == "딱 하나"


# --- 3. 가드 ---------------------------------------------------------------- #


def test_resurrection_mission_filtered():
    fake = _fake_llm(
        [
            {
                "title": "봄이 부활시키기",
                "description": "다시 살아나길.",
                "category": "rest",
            },
            {"title": "산책 가기", "description": "5분만.", "category": "activity"},
        ]
    )
    result = recommend(emotion_score=5, generate=fake, count=3)
    assert all("부활" not in m["title"] for m in result)


# --- 4. RAG 난이도 필터 (corpus 보강 후 난이도별 검색) ----------------------- #


def _capture_rag_where(monkeypatch):
    """recommend() 가 RAG 에 넘기는 where 필터를 가로채 담는다(ChromaDB 없이 검증)."""
    captured: dict = {}

    def fake_retrieve(query, k=3, *, where=None):
        captured["where"] = where
        return []  # 빈 결과 → 규칙 풀로 진행(graceful)

    monkeypatch.setattr(mission_mod, "_rag_retrieve", fake_retrieve)
    return captured


def test_rag_query_filters_by_category_and_difficulty(monkeypatch):
    """RAG 검색이 category=mission 과 난이도를 $and 로 함께 필터한다."""
    captured = _capture_rag_where(monkeypatch)
    recommend(emotion_score=2, count=3)  # 낮은 점수 → gentle
    assert captured["where"] == {
        "$and": [{"category": "mission"}, {"difficulty": "gentle"}]
    }


def test_rag_difficulty_follows_emotion_score(monkeypatch):
    """감정 점수에 따라 RAG 난이도 필터도 바뀐다(gentle/small/active)."""
    captured = _capture_rag_where(monkeypatch)
    for score, expected in [(2, "gentle"), (5, "small"), (9, "active")]:
        recommend(emotion_score=score, count=2)
        diffs = [
            cond["difficulty"]
            for cond in captured["where"]["$and"]
            if "difficulty" in cond
        ]
        assert diffs == [expected]


# --- 5. 수면 질 modifier (5단계 → 난이도 ±1티어, dead-zone 3축약) ----------- #


def test_sleep_poor_lowers_difficulty():
    """수면 나쁨(1·2) → 난이도 한 단계 내림."""
    assert mission_mod._apply_sleep("small", 1) == "gentle"
    assert mission_mod._apply_sleep("small", 2) == "gentle"
    assert mission_mod._apply_sleep("active", 2) == "small"


def test_sleep_good_raises_difficulty():
    """수면 좋음(4·5) → 난이도 한 단계 올림."""
    assert mission_mod._apply_sleep("small", 4) == "active"
    assert mission_mod._apply_sleep("small", 5) == "active"
    assert mission_mod._apply_sleep("gentle", 5) == "small"


def test_sleep_fair_keeps_difficulty():
    """수면 보통(3) → 그대로."""
    assert mission_mod._apply_sleep("small", 3) == "small"


def test_sleep_none_is_graceful():
    """수면 미입력(None) → 그대로(graceful)."""
    assert mission_mod._apply_sleep("small", None) == "small"


def test_sleep_clamps_at_bounds():
    """경계: gentle 아래·active 위로는 안 넘어감."""
    assert mission_mod._apply_sleep("gentle", 1) == "gentle"
    assert mission_mod._apply_sleep("active", 5) == "active"


def test_sleep_quality_feeds_recommend_difficulty(monkeypatch):
    """recommend(sleep_quality=…)가 난이도(=RAG 필터)에 반영된다."""
    captured = _capture_rag_where(monkeypatch)
    recommend(emotion_score=5, sleep_quality=1, count=2)  # small → 나쁨 → gentle
    diffs = [c["difficulty"] for c in captured["where"]["$and"] if "difficulty" in c]
    assert diffs == ["gentle"]
    recommend(emotion_score=5, sleep_quality=5, count=2)  # small → 좋음 → active
    diffs = [c["difficulty"] for c in captured["where"]["$and"] if "difficulty" in c]
    assert diffs == ["active"]


# --- 6. 레벨 기반 난이도 조합 (06-15, project_recovery_score_axes_redesign_260614) - #


def test_composition_l2_3_is_all_gentle():
    assert mission_mod.mission_composition("L2~3") == ("gentle", "gentle", "gentle")


def test_composition_l1_varies_with_emotion_score():
    """L1: 감정점수 낮음(<=3)→G×2+Sm×1, 그 외→G×1+Sm×2."""
    assert mission_mod.mission_composition("L1", emotion_score=2) == (
        "gentle",
        "gentle",
        "small",
    )
    assert mission_mod.mission_composition("L1", emotion_score=7) == (
        "gentle",
        "small",
        "small",
    )


def test_composition_l0_45_plus_is_single_active():
    assert mission_mod.mission_composition("L0", score=45) == ("active",)
    assert mission_mod.mission_composition("L0", score=100) == ("active",)


def test_composition_l0_below_45_matches_l1():
    """L0의 0~45 구간은 L1과 동일 구성(레벨/점수는 독립 축)."""
    assert mission_mod.mission_composition(
        "L0", score=30, emotion_score=2
    ) == mission_mod.mission_composition("L1", emotion_score=2)


def test_composition_unknown_level_is_none():
    """level=None(또는 미인식) → None, recommend()는 기존 단일난이도 동작."""
    assert mission_mod.mission_composition(None) is None


def test_recommend_with_level_l2_3_returns_three_gentle():
    result = recommend(emotion_score=2, level="L2~3")
    assert len(result) == 3
    assert [m["difficulty"] for m in result] == ["gentle", "gentle", "gentle"]
    titles = [m["title"] for m in result]
    assert len(set(titles)) == 3  # 중복 없음


def test_recommend_with_level_l1_mixed_difficulties():
    result = recommend(emotion_score=7, level="L1")
    assert [m["difficulty"] for m in result] == ["gentle", "small", "small"]
    for m in result:
        assert set(m) == {"title", "description", "category", "rationale", "difficulty"}


def test_recommend_with_level_l0_45_plus_returns_single_active():
    result = recommend(emotion_score=5, level="L0", recovery_score=50)
    assert len(result) == 1
    assert result[0]["difficulty"] == "active"


def test_recommend_level_none_keeps_old_behavior():
    """level 미지정 시 기존 동작(count개, 단일 난이도) 유지 + difficulty 태깅."""
    result = recommend(emotion_score=2, count=3)
    assert len(result) == 3
    for m in result:
        assert m["difficulty"] == "gentle"
