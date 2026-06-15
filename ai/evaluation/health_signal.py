"""⑧-확장: 수면·활동 객관데이터 → 회복점수 반영 (프로토타입).

⑧ 평가 확장: 삼성헬스(→Health Connect 경유)에서 받은 **수면·활동 객관데이터**를
회복점수에 더하고, 주관 감정 체크인과 **교차검증**한다.

설계: [recovery_signal.py](recovery_signal.py) 와 동일하게 **순수 함수** — 데이터 소스
(삼성헬스/더미/수동입력)와 분리. 입력만 넣으면 점수가 나온다. 그래서 GPU/DB/실연동
없이도 더미로 바로 테스트된다. (삼성헬스 실연동은 개발 빌드에서 같은 입력에 꽂으면 끝)

⚠️ 기존 `recovery_score()` 함수 자체는 **안 건드린다.** `compute_recovery_signal()` 이
**활동(걸음) 객관데이터가 들어올 때만** `blend_recovery_score`(40/35/25 + 활동10)로 교체
호출한다(미제공 시 기존 40/35/25 산식 그대로 — 하위호환). **수면은 회복점수서 제외**
(결정문서 회복점수_미션_결정_260611.md §2) — 점수 항이 아니라 교차검증·리포트 표시로만
쓴다. 가중치는 설계 판단이라 자유 조정.

가중치·임계값은 논문이 정해주는 값이 아니라 **설계 판단**(주석에 표시). 숫자는 자유롭게 조정.
"""

from __future__ import annotations

from typing import Any, Optional

# ── 가중치 — 핵심 3항은 결정문서 §1 정본(40/35/25) 유지, 활동은 객관 add-on. ──
# 수면은 회복점수서 제외(결정문서 §2): 점수 항 아님 → 교차검증·리포트 표시로만.
W_EMOTION = 40.0  # 주관 감정 평균
W_MISSION = 35.0  # 미션 누적(천장)
W_CONSISTENCY = 25.0  # 체크인 꾸준함
W_ACTIVITY = 10.0  # 활동 객관(걸음) — 설계 add-on. 들어올 때만 분모 포함(옵션 A).
# 미션 만점 기준(개수). 결정문서 §1 정본 천장 35 와 일치 → base(recovery_score)와
# blend 의 미션 환산이 동일(미션당 1점). 캡이 다르면 base→blend 전환 시 활동과
# 무관하게 점수가 튀어 "핵심 40/35/25 불변"이 깨짐(reviewer 2026-06-11 발견).
_MISSION_CAP = 35.0

# ── 교차검증 임계값(설계 판단) ──
_SLEEP_BAD = 40.0  # 수면점수 이 미만이면 '나쁨'
_SLEEP_GOOD = 70.0  # 이 이상이면 '좋음'
_EMOTION_GOOD = 6.0  # 감정 평균(1~10) 이 이상이면 '좋음'
_EMOTION_BAD = 4.0  # 이 이하면 '나쁨'

# ── 활동량 정규화 기준(설계 판단) ──
_STEPS_TARGET = 6000  # 이 걸음수를 100점으로 (06-15: 활동 유도 위해 8000→6000)

# ── 생활패턴(15%) 축 합성 가중치 — 걸음40/수면30/앱사용량30 (06-15 합의) ──
W_LIFESTYLE_STEPS = 0.40
W_LIFESTYLE_SLEEP = 0.30
W_LIFESTYLE_PHONE = 0.30

_SLEEP_HOURS_TARGET = 6.0  # 수면 첫주 고정기준 — 이 시간을 100점으로
_NIGHT_USAGE_PER_PENALTY_MIN = 10.0  # 새벽(2~6시) 사용 이 분(分)마다 -1점
_PERSONALIZE_MIN_HISTORY = 7  # 이만큼 기록이 쌓이면 개인화(최근 평균 대비 비율)로 전환


def sleep_to_score(
    sleep_score: Optional[float] = None, sleep_hours: Optional[float] = None
) -> Optional[float]:
    """수면 → 0~100 점수.

    - 삼성헬스 **수면점수(0~100)** 가 있으면 그대로 사용(가장 정확).
    - 없고 **수면시간** 만 있으면 7~9시간을 최적(100)으로 보고 환산.
    - 둘 다 없으면 None(graceful — 점수에서 수면 항 0 취급).
    """
    if sleep_score is not None:
        return max(0.0, min(100.0, float(sleep_score)))
    if sleep_hours is not None:
        h = float(sleep_hours)
        # 8h 중심, ±1h 까지 만점, 멀어질수록 감점(설계 판단).
        if 7.0 <= h <= 9.0:
            return 100.0
        gap = 7.0 - h if h < 7.0 else h - 9.0
        return max(0.0, 100.0 - gap * 20.0)  # 1시간 벗어날 때마다 20점
    return None


def activity_to_score(steps: Optional[int] = None) -> Optional[float]:
    """활동(걸음수) → 0~100 점수. 목표 걸음(_STEPS_TARGET)을 100으로 선형 환산.

    ⚠️ steps=0 은 "실제 0걸음"으로 보고 0점 반환(None 아님). "측정 안 됨"은 None 으로
    구분해 호출부에서 넘긴다(어댑터 `total_steps` 는 레코드 없으면 None).
    """
    if steps is None:
        return None
    return max(0.0, min(100.0, float(steps) / _STEPS_TARGET * 100.0))


def night_usage_to_score(night_minutes: Optional[float] = None) -> Optional[float]:
    """새벽(2~6시) 폰사용 분(分) → 0~100 점수. 100점에서 시작해 10분당 -1점.

    ⚠️ `sleep_to_score`와는 별도 — 회복점수 점수 항이 아니라 생활패턴 축의
    앱사용량 신호로만 쓰인다.
    """
    if night_minutes is None:
        return None
    return max(0.0, min(100.0, 100.0 - float(night_minutes) / _NIGHT_USAGE_PER_PENALTY_MIN))


def _personalized_ratio(today: float, history: Optional[list[float]]) -> Optional[float]:
    """최근 기록이 `_PERSONALIZE_MIN_HISTORY`일 이상이면 '최근 평균 대비 오늘' 비율(cap 100).

    기록이 부족하면 None(호출부에서 첫주 고정기준으로 대체).
    """
    if not history or len(history) < _PERSONALIZE_MIN_HISTORY:
        return None
    avg = sum(history) / len(history)
    if avg <= 0:
        return 100.0  # 평소도 0이면 "평소와 같음" = 변화 없음으로 본다
    return max(0.0, min(100.0, today / avg * 100.0))


def sleep_pattern_score(
    sleep_hours: Optional[float] = None, *, history: Optional[list[float]] = None
) -> Optional[float]:
    """수면시간 → 생활패턴(15%) 축의 수면(30%) 점수.

    - 첫주(기록 `_PERSONALIZE_MIN_HISTORY`일 미만): 고정기준 — `_SLEEP_HOURS_TARGET`시간=100점.
    - 이후: 개인화 — 최근 기록 평균 대비 오늘 수면시간 비율(cap 100).
    """
    if sleep_hours is None:
        return None
    personalized = _personalized_ratio(float(sleep_hours), history)
    if personalized is not None:
        return personalized
    return max(0.0, min(100.0, float(sleep_hours) / _SLEEP_HOURS_TARGET * 100.0))


def night_usage_pattern_score(
    night_minutes: Optional[float] = None, *, history: Optional[list[float]] = None
) -> Optional[float]:
    """새벽(2~6시) 폰사용 분 → 생활패턴(15%) 축의 앱사용량(30%) 점수.

    - 첫주(기록 `_PERSONALIZE_MIN_HISTORY`일 미만): 고정기준 — `night_usage_to_score`(10분당 -1점) 그대로.
    - 이후: 개인화 — 최근 기록의 `night_usage_to_score` 평균 대비 오늘 비율(cap 100).
    """
    raw_today = night_usage_to_score(night_minutes)
    if raw_today is None:
        return None
    raw_history = None
    if history:
        raw_history = [r for m in history if (r := night_usage_to_score(m)) is not None]
    personalized = _personalized_ratio(raw_today, raw_history)
    if personalized is not None:
        return personalized
    return raw_today


def lifestyle_pct(
    steps: Optional[int] = None,
    sleep_hours: Optional[float] = None,
    night_minutes: Optional[float] = None,
    *,
    sleep_history: Optional[list[float]] = None,
    night_minutes_history: Optional[list[float]] = None,
) -> Optional[float]:
    """생활패턴(15%) 축 합성 점수 — 걸음40%/수면30%/앱사용량30% (06-15 합의).

    `recovery_score_from_axes`의 `lifestyle_pct` 인자에 그대로 넘긴다. 무페널티
    재정규화 — 값이 없는 항목은 분모에서 제외하고 나머지로 재정규화한다(전부
    없으면 None → 생활패턴 축 자체가 빠짐, `recovery_score_from_axes`와 동일 패턴).
    """
    parts: list[tuple[float, float]] = []
    a = activity_to_score(steps)
    if a is not None:
        parts.append((a, W_LIFESTYLE_STEPS))
    s = sleep_pattern_score(sleep_hours, history=sleep_history)
    if s is not None:
        parts.append((s, W_LIFESTYLE_SLEEP))
    p = night_usage_pattern_score(night_minutes, history=night_minutes_history)
    if p is not None:
        parts.append((p, W_LIFESTYLE_PHONE))

    if not parts:
        return None
    total_w = sum(w for _, w in parts)
    return round(sum(v * w for v, w in parts) / total_w, 1)


def blend_recovery_score(
    emotion_avg: float,
    completed_missions: int = 0,
    consistency_pct: Optional[float] = None,
    activity_score: Optional[float] = None,
) -> int:
    """회복점수(0~100) — 감정·미션·꾸준함(핵심 40/35/25) + **활동** 가중합.

    ⚠️ 수면은 점수 항이 아니다(결정문서 §2 "수면 회복점수서 제외"). 수면 신호는
    `cross_check`·리포트 표시에서만 쓴다.

    옵션 A(재정규화): 빠진 **외부 신호(활동)** 는 분모에서 제외한다 → 데이터가 없다고
    점수가 깎이지 않는다. 핵심 항(감정·미션·꾸준함)은 항상 분모에 포함. 각 항은
    0~1 비율 × 가중치, 최종 = 포함된 가중치 합으로 나눠 0~100 정규화.
    """
    parts: list[tuple[float, float]] = [
        (max(0.0, min(1.0, (emotion_avg - 1) / 9)), W_EMOTION),
        (min(float(completed_missions), _MISSION_CAP) / _MISSION_CAP, W_MISSION),
        (max(0.0, min(1.0, (consistency_pct or 0.0) / 100)), W_CONSISTENCY),
    ]
    if activity_score is not None:  # 외부 신호 — 있을 때만 분모에 포함
        parts.append((max(0.0, min(1.0, activity_score / 100)), W_ACTIVITY))
    total_w = sum(w for _, w in parts)
    if total_w == 0:
        return 0
    return max(0, min(100, round(sum(frac * w for frac, w in parts) / total_w * 100)))


def cross_check(
    sleep_score: Optional[float], emotion_avg: Optional[float]
) -> dict[str, Any]:
    """객관(수면) vs 주관(감정) 교차검증. 점수는 안 깎고 **플래그+근거문장**만.

    "센서는 나쁘다는데 본인은 괜찮다더라"(주관·객관 불일치) 케이스를 잡는다.

    ⚠️ `note` 는 **사별 보호자에게 그대로 보일 수 있는** 문장(evidence 합류)이라
    비낙인·따뜻한 톤으로 쓴다. 임상 해석("숨기는 중"·"추가 관찰")은 `status` 코드로만
    남기고(수의사 콘솔용), 보호자 노출 문장에는 넣지 않는다.
    """
    if sleep_score is None or emotion_avg is None:
        return {"status": "unknown", "mismatch": False, "note": None}

    sleep_bad = sleep_score < _SLEEP_BAD
    sleep_good = sleep_score >= _SLEEP_GOOD
    emo_good = emotion_avg >= _EMOTION_GOOD
    emo_bad = emotion_avg <= _EMOTION_BAD

    if sleep_bad and emo_good:
        return {
            "status": "mismatch_high_risk",
            "mismatch": True,
            "note": "센서 기록상 수면이 부족했던 것 같아요. 오늘은 자신을 조금 더 아껴주세요.",
        }
    if sleep_good and emo_bad:
        return {
            "status": "mismatch",
            "mismatch": True,
            "note": "수면은 괜찮았는데 마음이 무거운 날이네요. 그런 날도 있어요, 천천히 가요.",
        }
    if sleep_bad and emo_bad:
        return {
            "status": "agree_low",
            "mismatch": False,
            "note": "몸도 마음도 지친 날이에요. 무리하지 말고 충분히 쉬어주세요.",
        }
    return {"status": "agree_ok", "mismatch": False, "note": None}


def condition_signal(
    emotion_avg: float,
    *,
    sleep_score: Optional[float] = None,
    sleep_hours: Optional[float] = None,
) -> dict[str, Any]:
    """객관 수면 + 주관 감정 → **오늘 컨디션** 추정 + 신뢰도(교차검증).

    회복점수(콘텐츠 해금 게이트)와 **별개 출력**이다. 강사 구상: "주관 체크인뿐 아니라
    삼성헬스 객관 수면을 함께 반영해 컨디션/스트레스를 추정"(점수 게이트는 결정문서 §2로
    수면 제외 — 여기선 게이트를 안 건드리고 컨디션만 본다).

    Returns: ``{condition, confidence, sleep_score, cross_check, message}``
    - ``condition``: ``"양호"`` / ``"주의"`` / ``"보통"``
    - ``confidence``: ``"높음"``(수면·감정 일치) / ``"낮음"``(불일치 — 교차검증 플래그)
    - 수면이 없으면 감정 단독 추정(confidence 보수적으로 "낮음").

    예) 수면점수 82 + 기분 좋음 → 양호/높음 · 수면 나쁨 + 기분 나쁨 → 주의/높음(일치)
        수면 나쁨 + 기분 좋음 → 주의/낮음(센서는 나쁜데 괜찮다 = 숨은 위험)
    """
    s = sleep_to_score(sleep_score, sleep_hours)
    check = cross_check(s, emotion_avg)

    emo_good = emotion_avg >= _EMOTION_GOOD
    emo_bad = emotion_avg <= _EMOTION_BAD

    if check["status"] == "mismatch_high_risk":
        condition = "주의"  # 센서상 수면 부족인데 본인은 괜찮다 → 숨은 위험
    elif emo_bad:
        # 기분이 나쁜 날은 수면 유무·질과 무관하게 '주의'(사별 케어 — 안전쪽으로 기울임).
        condition = "주의"
    elif emo_good and (s is None or s >= _SLEEP_GOOD):
        condition = "양호"
    else:
        condition = "보통"

    confidence = "낮음" if (check["mismatch"] or s is None) else "높음"
    message = check["note"] or (
        "오늘 컨디션은 양호해 보여요." if condition == "양호" else None
    )
    return {
        "condition": condition,
        "confidence": confidence,
        "sleep_score": s,
        "cross_check": check,
        "message": message,
    }


def health_signal(
    emotion_avg: float,
    *,
    completed_missions: int = 0,
    consistency_pct: Optional[float] = None,
    sleep_score: Optional[float] = None,
    sleep_hours: Optional[float] = None,
    steps: Optional[int] = None,
) -> dict[str, Any]:
    """수면·활동까지 묶은 회복 신호 한 방. 화면/발표에 그대로 쓸 dict 반환."""
    s_score = sleep_to_score(sleep_score, sleep_hours)
    a_score = activity_to_score(steps)
    # 수면은 점수서 제외(결정문서 §2) → blend엔 활동만. 수면은 cross_check·표시로만.
    index = blend_recovery_score(
        emotion_avg, completed_missions, consistency_pct, a_score
    )
    check = cross_check(s_score, emotion_avg)

    evidence: list[str] = [f"감정 평균 {round(emotion_avg, 1)}/10"]
    if s_score is not None:
        evidence.append(f"수면점수 {round(s_score)}/100 (참고 — 점수 미반영)")
    if a_score is not None:
        evidence.append(f"활동 {round(a_score)}/100 ({steps}걸음)")
    if check["note"]:
        evidence.append(f"⚠ {check['note']}")

    return {
        "recovery_index": index,
        "sleep_score": s_score,
        "activity_score": a_score,
        "cross_check": check,
        "evidence": evidence,
    }


if __name__ == "__main__":
    import sys

    # Windows 기본 콘솔(cp949)에서 ⚠ 등 유니코드 출력 크래시 방지.
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    # 더미 시나리오 — 삼성헬스 없이 로직 검증.
    scenarios = [
        (
            "좋음 일치",
            dict(
                emotion_avg=8,
                completed_missions=10,
                consistency_pct=80,
                sleep_score=82,
                steps=9000,
            ),
        ),
        (
            "나쁨 일치",
            dict(
                emotion_avg=3,
                completed_missions=2,
                consistency_pct=30,
                sleep_score=35,
                steps=1500,
            ),
        ),
        (
            "센서 나쁨·본인 좋다",
            dict(
                emotion_avg=8,
                completed_missions=5,
                consistency_pct=50,
                sleep_score=32,
                steps=2000,
            ),
        ),
        ("수면시간만 있음", dict(emotion_avg=6, sleep_hours=5.5, steps=6000)),
    ]
    for name, kw in scenarios:
        out = health_signal(**kw)
        print(f"\n[{name}]  회복점수 = {out['recovery_index']}")
        print(f"  교차검증: {out['cross_check']['status']}")
        for e in out["evidence"]:
            print(f"  - {e}")
