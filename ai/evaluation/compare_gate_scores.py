"""게이트 교체 영향 비교 — 옛 `recovery_score`(절대 감정) vs 새 `recovery_score_from_axes`(감정 추세).

세종님 게이트 교체(backend `emotion.py`) 리뷰용 자료. 같은 사용자 시나리오에서 두
산식의 점수와 게이트 단계(locked/teaser/open, 80점 기준)가 얼마나 달라지는지 보여
임계값(45·80)을 그대로 둬도 되는지 **수치로** 판단하게 한다.

실행: `python -m ai.evaluation.compare_gate_scores` (또는 이 파일 직접 실행).

⚠️ 옛 산식 입력(완료 누적수·꾸준함%·감정평균)은 현재 백엔드 `get_recovery` 가
DB에서 뽑는 방식 그대로 시나리오에서 역산한다(공정 비교). 새 산식은 원자료
(미션·체크인 리스트)를 그대로 넣는다.
"""

from __future__ import annotations

from datetime import date, timedelta

from .recovery_signal import (
    _CONSISTENCY_WINDOW,
    recovery_score,
    recovery_score_from_axes,
)

_GATE_OPEN = 80  # emotion.py 게이트: recovery_pct >= 80 → open


def _gate(pct: int) -> str:
    """게이트 단계(content_unlocked 가정). 점수만으로 locked 제외하고 비교."""
    return "open" if pct >= _GATE_OPEN else "teaser"


def _missions_over_days(
    specs: list[tuple[int, int, int, bool]], anchor: date
) -> list[dict]:
    """일자별 (며칠전, 배정수, 완료수, active완료여부) → 미션 리스트(새 함수 입력).

    `date` 는 배정일(anchor - 며칠전). 앞에서부터 완료수만큼 done=True.
    active완료여부=True 면 그날 완료분 중 첫 건을 difficulty=active 로.
    """
    out: list[dict] = []
    for days_ago, assigned, completed, active_done in specs:
        d = (anchor - timedelta(days=days_ago)).isoformat()
        for i in range(assigned):
            done = i < completed
            diff = "active" if (active_done and i == 0 and done) else "gentle"
            out.append({"date": d, "done": done, "difficulty": diff})
    return out


def _old_inputs(missions: list[dict], checkins: list[dict], anchor: date) -> tuple:
    """백엔드 get_recovery 방식으로 옛 산식 입력 역산.

    - completed_missions = 완료 누적수(sticky count, 천장 40)
    - consistency_pct = 최근 14일 중 '완료한 날 수' / 14 × 100 (백엔드와 동일)
    - emotion_avg = 체크인 점수 평균
    """
    completed_missions = sum(1 for m in missions if m.get("done"))
    done_days = {
        m["date"]
        for m in missions
        if m.get("done")
        and 0 <= (anchor - date.fromisoformat(m["date"])).days < _CONSISTENCY_WINDOW
    }
    consistency_pct = round(len(done_days) / _CONSISTENCY_WINDOW * 100)
    scores = [c["score"] for c in checkins]
    emotion_avg = round(sum(scores) / len(scores), 1) if scores else 0.0
    return completed_missions, consistency_pct, emotion_avg


def _checkins(scores: list[float], anchor: date) -> list[dict]:
    """오래된→최근 점수 → 체크인 목록(하루 간격)."""
    n = len(scores)
    return [
        {"score": s, "created_at": (anchor - timedelta(days=n - 1 - i)).isoformat()}
        for i, s in enumerate(scores)
    ]


def _persona(name: str, mission_specs: list[tuple], emotion_scores: list[float]) -> dict:
    anchor = date(2026, 6, 15)
    missions = _missions_over_days(mission_specs, anchor)
    checkins = _checkins(emotion_scores, anchor)
    comp, cons_pct, avg = _old_inputs(missions, checkins, anchor)
    old = recovery_score(
        emotion_avg=avg, completed_missions=comp, consistency_pct=cons_pct
    )
    new = recovery_score_from_axes(missions, checkins, as_of=anchor)
    return {
        "name": name,
        "old": old,
        "new": new,
        "delta": new - old,
        "gate_old": _gate(old),
        "gate_new": _gate(new),
    }


# 대표 시나리오 — 옛/새 산식이 갈리는 지점을 일부러 노린다.
PERSONAS = [
    # (며칠전, 배정3, 완료, active완료) × 여러 날
    (
        "꾸준 회복자(28일 매일 전부완료·감정상승)",
        [(d, 3, 3, False) for d in range(28)],
        [3, 4, 5, 6, 7, 8],
    ),
    (
        "초반 몰아서 후 2주 잠수(sticky 함정)",
        [(d, 3, 3, False) for d in range(20, 28)],  # 20~27일 전에만 완료, 최근 0
        [5, 5, 6, 6],
    ),
    (
        "감정 악화(미션은 꾸준)",
        [(d, 3, 3, False) for d in range(14)],
        [8, 8, 4, 3, 2, 2],  # 추세 하락
    ),
    (
        "부분완료 상습(매일 3중 2)",
        [(d, 3, 2, False) for d in range(14)],
        [5, 5, 6, 6],
    ),
    (
        "신규(체크인 2회·미션 소량)",
        [(0, 3, 3, False), (1, 3, 2, False)],
        [5, 6],
    ),
]


def main() -> None:
    rows = [_persona(*p) for p in PERSONAS]
    w = max(len(r["name"]) for r in rows)
    print(f"{'시나리오':<{w}}  옛점수  새점수   Δ   게이트(옛→새)")
    print("-" * (w + 36))
    for r in rows:
        print(
            f"{r['name']:<{w}}  {r['old']:>5}  {r['new']:>5}  {r['delta']:>+4}   "
            f"{r['gate_old']}→{r['gate_new']}"
        )
    print(
        "\n게이트는 80점=open 기준(content_unlocked는 별도 충족 가정). "
        "Δ가 크고 게이트가 바뀌는 행이 임계값 재검토 대상."
    )


if __name__ == "__main__":
    main()
