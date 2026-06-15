"""⑧-확장: 휴대폰 앱 사용 로그 → 행동 패턴(digital phenotyping) 분석 — 정량.

목표(팀원 로그 수집 LV1 완료 → LV2~LV4): "어떤 앱을 / 얼마나 / 언제(심야) 썼는지"
원시 로그를 받아, **사회적 위축·도피적 소비·생활 리듬 교란·사용 급증** 같은
행동 변화 신호를 뽑아냅니다. **진단이 아니라 '변화 감지' 수준**입니다.

설계: [recovery_signal.py](recovery_signal.py)·[report.py](report.py) 와 동일하게 **순수 함수**.
DB/수집은 백엔드·수집 담당이 하고, 여기엔 조회 결과(리스트)를 넣어 줍니다.
그래야 단말·DB 없이 테스트·시뮬레이션이 됩니다.

⚠️ 개인정보 최소화 ([logs.py](logs.py)·../CLAUDE.md):
   - 2026-06-12 — **카테고리 분류는 클라이언트(수집기)가 끝내고** `category`
     (ENTERTAINMENT/SOCIAL/EDUCATION/FINANCE) 4종만 보냅니다. raw 패키지명은
     아예 들어오지 않습니다(수집 단계에서 비식별 완료) — `categorize()`/패키지
     키워드 매핑은 더 이상 필요 없어 제거했습니다.
   - 출력은 **추세·비중·시각** 같은 비식별 지표만. "무슨 영상을 봤는지" 류는 다루지 않습니다.

⚠️ 경계(../CLAUDE.md §0, ../ai/CLAUDE.md §0/§5):
   - 이 신호는 **회복 점수(40/35/25)에 들어가지 않습니다.** 수면 신호 결정과 동일하게
     *표시지표 + 미션 강도 보조 + advisory* 로만 씁니다. ([recovery_signal.recovery_score] 불변)
   - `concern_level` 은 참고용입니다. **위기(1393)·crisis 자동 트리거 금지** — 위기 판정은
     대화 기반 safety 레이어의 몫. 여기 신호는 "더 세심히 보라"는 힌트까지만.

핵심 해석 원칙(recovery_signal 과 동일 결): "빈도/시간의 *변화*"를 봅니다.
- 일상 기능 앱(교육·금융)이 줄고 엔터테인먼트·SNS만 남으면 → **행동 반경 축소(위축)**.
- 심야 사용이 늘고 취침이 늦어지면 → **생활 리듬 교란**.
- 특정 카테고리가 평소의 몇 배로 튀면 → **스트레스/사건 가능성(급증)**.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Final, Iterable, Optional

# --- 신호 라벨 (헤드라인) ---------------------------------------------------- #
SIGNAL_STABLE: Final = "안정"  # 일상 리듬 유지
SIGNAL_WITHDRAWING: Final = "활동 위축"  # 외출·일상 앱 감소 + 수동 소비 증가
SIGNAL_DISRUPTED: Final = "생활 리듬 교란"  # 심야 사용·취침 지연
SIGNAL_SPIKE: Final = "사용 급증"  # 특정 카테고리 폭증(스트레스/사건)
SIGNAL_INSUFFICIENT: Final = "데이터 부족"

# --- 앱 카테고리 (클라이언트가 보내는 4종 + other) ---------------------------- #
# 2026-06-12 — 클라이언트(수집기)가 패키지명을 이미 이 4종으로 분류해 보낸다.
CAT_ENTERTAINMENT: Final = "entertainment"  # 동영상·게임 등 — 수동 소비/수면 교란
CAT_SOCIAL: Final = "social"  # SNS — 도피/반추 가능
CAT_EDUCATION: Final = "education"  # 인강·학습 — 일상 기능
CAT_FINANCE: Final = "finance"  # 은행·결제 — 일상 기능
CAT_OTHER: Final = "other"  # 미분류(클라이언트가 4종 중 못 정한 항목)

_KNOWN_CATEGORIES: Final = frozenset(
    {CAT_ENTERTAINMENT, CAT_SOCIAL, CAT_EDUCATION, CAT_FINANCE}
)

# 일상 기능 앱 — 줄면 '행동 반경 축소(위축)' 근거.
ACTIVE_LIFE: Final = frozenset({CAT_EDUCATION, CAT_FINANCE})
# 수동·도피적 소비 — 비중이 커지면 위축/수면 교란 맥락.
PASSIVE: Final = frozenset({CAT_ENTERTAINMENT, CAT_SOCIAL})

# 카테고리 한글 라벨(근거 문장용).
CATEGORY_LABEL: Final[dict[str, str]] = {
    CAT_ENTERTAINMENT: "엔터테인먼트",
    CAT_SOCIAL: "SNS",
    CAT_EDUCATION: "교육",
    CAT_FINANCE: "금융",
    CAT_OTHER: "기타",
}

# 심야 시간대(23:00~05:59) — 수면 교란 신호.
LATE_NIGHT_HOURS: Final[frozenset[int]] = frozenset({23, 0, 1, 2, 3, 4, 5})

# --- 임계값 (이름으로 의미를 드러냄) ----------------------------------------- #
_MIN_DAYS: Final = 4  # 신호를 내기 위한 최소 관측 일수
_DEFAULT_WINDOW: Final = 14  # 기본 분석 창(일) — 7/14/30 중 중간값
_SPIKE_RATIO: Final = 3.0  # 평소 대비 '급증' 배수
_SPIKE_MIN_MINUTES: Final = 60.0  # 급증 인정 최소 절대량(노이즈 컷)
_PASSIVE_HIGH: Final = 0.60  # 수동 소비 비중 경고선(60%)
_ACTIVE_DROP: Final = 0.10  # 외출·일상 앱 비중 '의미있는' 감소폭(10%p)
_LATE_NIGHT_WATCH: Final = 60.0  # 심야 사용 주의선(분/일)
_BEDTIME_LATER: Final = 30.0  # 취침 '늦어짐' 인정폭(분)


# --- 카테고리 정규화 --------------------------------------------------------- #
def normalize_category(category: Optional[str]) -> str:
    """클라이언트 카테고리(대소문자 무관)를 내부 키로 정규화합니다.

    클라이언트는 ``ENTERTAINMENT``/``SOCIAL``/``EDUCATION``/``FINANCE`` 4종을
    보낸다(대소문자 무관). 그 외 값·빈 값은 ``other``로 묶습니다.
    """
    if not category:
        return CAT_OTHER
    cat = str(category).strip().lower()
    return cat if cat in _KNOWN_CATEGORIES else CAT_OTHER


# --- 내부 헬퍼 --------------------------------------------------------------- #
def _parse_day(token: Any) -> Optional[date]:
    try:
        return date.fromisoformat(str(token)[:10])
    except (ValueError, TypeError):
        return None


def _late_minutes(rec: dict[str, Any]) -> float:
    """기록 한 건의 심야(23~06시) 사용 분. `late_night_minutes` 우선, 없으면 `by_hour` 합산."""
    if rec.get("late_night_minutes") is not None:
        return float(rec["late_night_minutes"] or 0)
    by_hour = rec.get("by_hour")
    if isinstance(by_hour, dict):
        return float(
            sum(float(m or 0) for h, m in by_hour.items() if int(h) in LATE_NIGHT_HOURS)
        )
    return 0.0


def _last_active_eff_hour(rec: dict[str, Any]) -> Optional[float]:
    """그 날 마지막 활동 시각(취침 추정용). 00~11시는 +24 로 보정해 자정 넘김을 정렬.

    `by_hour` 가 있을 때만. 저녁(18시)부터의 활동만 봐서 낮 사용에 휘둘리지 않게 합니다.
    """
    by_hour = rec.get("by_hour")
    if not isinstance(by_hour, dict):
        return None
    eff_hours: list[int] = []
    for h, m in by_hour.items():
        hour = int(h)
        if float(m or 0) > 0 and (hour >= 18 or hour < 12):
            eff_hours.append(hour + 24 if hour < 12 else hour)
    return float(max(eff_hours)) if eff_hours else None


def _bedtime_to_minutes(token: Any) -> Optional[float]:
    """'HH:MM' 취침시각 → 18시 기준 분. 00~11시는 +24h(다음날 새벽)로 보정."""
    try:
        hh, mm = str(token).split(":")[:2]
        h, m = int(hh), int(mm)
    except (ValueError, AttributeError):
        return None
    eff_h = h + 24 if h < 12 else h
    return eff_h * 60 + m


def _minutes_to_clock(eff_minutes: float) -> str:
    """18시 기준 분 → 'HH:MM' 표시(자정 넘김 복원)."""
    total = int(round(eff_minutes))
    hh = (total // 60) % 24
    mm = total % 60
    return f"{hh:02d}:{mm:02d}"


def _direction(delta: float, eps: float) -> str:
    return "증가" if delta > eps else "감소" if delta < -eps else "유지"


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


# --- 본체 ------------------------------------------------------------------- #
def analyze_phone_usage(
    usage_records: Iterable[dict[str, Any]],
    *,
    sleep_records: Iterable[dict[str, Any]] = (),
    as_of: Optional[date] = None,
    window_days: int = _DEFAULT_WINDOW,
) -> dict[str, Any]:
    """앱 사용 로그에서 행동 변화 신호를 산출합니다(순수 함수).

    Args:
        usage_records: 일별·카테고리별 사용 기록. 한 건의 형태(2026-06-12, 클라이언트가
            이 계약으로 맞춤 — raw 패키지명 없음, 비식별 완료):
            ``{"date": "YYYY-MM-DD", "category": "ENTERTAINMENT",
               "minutes": 234.0,
               # LV2(시간대 분석) 산출물 — 없으면 graceful:
               "late_night_minutes": 56.0,         # 새벽(0~6시) 사용 분(있으면 우선)
               "by_hour": {1: 30, 2: 26}}}         # (선택) 시간 단위 분 — 있으면 심야·취침 자동 산출``
            `category` 는 ``ENTERTAINMENT``/``SOCIAL``/``EDUCATION``/``FINANCE``
            4종(대소문자 무관) — `normalize_category` 로 정규화, 그 외 값은 ``other``.
            ⚠️ 실제 LV2 수집기는 **4개 버킷**(새벽0-6·아침6-12·오후12-18·저녁18-24)만 주고
            시간 단위(`by_hour`)는 주지 않습니다 → 수집기의 **카테고리별 '새벽(0-6)' 분**을
            `late_night_minutes` 에 그대로 넣어 주세요(그 값이 심야 신호의 정본).
            `by_hour` 는 더 잘게 쪼개진 데이터가 생길 때만 쓰는 선택 입력입니다.
        sleep_records: (선택, LV3 삼성헬스 연동) 일별 수면 기록.
            ``{"date": "YYYY-MM-DD", "sleep_score": 52, "bedtime": "01:10"}``.
            ⚠️ LV2 는 시간 단위가 없어 **취침시각 역산은 LV3 `bedtime` 에 의존**합니다
            (by_hour 추정 폴백은 더 잘게 쪼갠 데이터가 있을 때만). 없으면 취침 추세 생략.
        as_of: 분석 기준일. 보통 ``date.today()``. 이 날부터 과거 `window_days` 만 봅니다.
            None 이면 기록의 최신 날짜 기준(하위호환·결정적).
        window_days: 분석 창(일). 창을 앞(평소)·뒤(최근) 절반으로 갈라 '변화'를 봅니다.

    Returns:
        ``{signal, window, days_observed, screen_time, late_night, category_mix,
           active_life, app_diversity, spikes, bedtime, sleep_link, findings,
           evidence, reason, concern_level, mission_intensity_modifier}``.
        ``evidence`` 는 화면에 그대로 노출 가능한 근거 문장. ``concern_level`` 은 advisory
        (0 정상 / 1 관찰 / 2 주의) — **위기 자동 트리거 아님**.
    """
    # 1) 카테고리 정규화 + 날짜 파싱 + 창 필터. raw 패키지명은 없음(클라이언트가 비식별 완료).
    per_day_cat: dict[date, dict[str, float]] = {}
    per_day_late: dict[date, float] = {}
    per_day_lastact: dict[date, float] = {}
    for rec in usage_records:
        day = _parse_day(rec.get("date"))
        if day is None:
            continue
        minutes = float(rec.get("minutes") or 0)
        cat = normalize_category(rec.get("category"))
        bucket = per_day_cat.setdefault(day, {})
        bucket[cat] = bucket.get(cat, 0.0) + minutes
        per_day_late[day] = per_day_late.get(day, 0.0) + _late_minutes(rec)
        last = _last_active_eff_hour(rec)
        if last is not None:
            per_day_lastact[day] = max(per_day_lastact.get(day, 0.0), last)

    days = sorted(per_day_cat)
    if as_of is not None:
        days = [d for d in days if 0 <= (as_of - d).days < window_days]
    else:
        days = days[-window_days:]

    if len(days) < _MIN_DAYS:
        return {
            "signal": SIGNAL_INSUFFICIENT,
            "window": {"days": window_days, "as_of": str(as_of) if as_of else None},
            "days_observed": len(days),
            "screen_time": None,
            "late_night": None,
            "category_mix": None,
            "active_life": None,
            "app_diversity": None,
            "spikes": [],
            "bedtime": None,
            "sleep_link": None,
            "findings": [],
            "evidence": [
                f"관측일이 {len(days)}일뿐이라 행동 패턴을 읽기 어려워요(최소 {_MIN_DAYS}일)."
            ],
            "reason": "사용 기록이 더 쌓이면 행동 변화 추이를 보여드릴게요.",
            "concern_level": 0,
            "mission_intensity_modifier": 0,
        }

    # 2) 창을 앞(평소)·뒤(최근) 절반으로. recovery_signal._split_avg 와 동일 결.
    mid = len(days) // 2
    older_days = days[:mid] or days[:1]
    recent_days = days[mid:]

    def _cat_minutes(day_list: list[date]) -> dict[str, float]:
        """기간 합계(카테고리별 총 분)."""
        agg: dict[str, float] = {}
        for d in day_list:
            for c, m in per_day_cat[d].items():
                agg[c] = agg.get(c, 0.0) + m
        return agg

    def _daily_total(day_list: list[date]) -> list[float]:
        return [sum(per_day_cat[d].values()) for d in day_list]

    def _daily_group(day_list: list[date], group: frozenset[str]) -> list[float]:
        return [
            sum(m for c, m in per_day_cat[d].items() if c in group) for d in day_list
        ]

    def _daily_diversity(day_list: list[date]) -> list[float]:
        return [
            float(sum(1 for c, m in per_day_cat[d].items() if m > 0 and c != CAT_OTHER))
            for d in day_list
        ]

    findings: list[dict[str, Any]] = []
    evidence: list[str] = []

    # 3) 스크린타임 추세
    st_older, st_recent = _mean(_daily_total(older_days)), _mean(
        _daily_total(recent_days)
    )
    st_delta = st_recent - st_older
    screen_time = {
        "older": round(st_older, 1),
        "recent": round(st_recent, 1),
        "delta": round(st_delta, 1),
        "direction": _direction(st_delta, 5.0),
        "unit": "분/일",
    }
    evidence.append(
        f"하루 스크린타임 {screen_time['older']}→{screen_time['recent']}분 ({screen_time['direction']})"
    )

    # 4) 심야 사용 추세
    ln_older = _mean([per_day_late.get(d, 0.0) for d in older_days])
    ln_recent = _mean([per_day_late.get(d, 0.0) for d in recent_days])
    late_night = {
        "older": round(ln_older, 1),
        "recent": round(ln_recent, 1),
        "delta": round(ln_recent - ln_older, 1),
        "direction": _direction(ln_recent - ln_older, 5.0),
        "unit": "분/일",
    }
    has_hourly = any(d in per_day_lastact for d in days) or any(
        per_day_late.get(d, 0.0) > 0 for d in days
    )
    if has_hourly and ln_recent >= _LATE_NIGHT_WATCH and ln_recent >= ln_older:
        sev = 2 if ln_recent >= 2 * _LATE_NIGHT_WATCH else 1
        findings.append(
            {"code": "late_night_use", "bucket": "disrupted", "severity": sev}
        )
        evidence.append(
            f"심야(23~06시) 사용 {late_night['older']}→{late_night['recent']}분 "
            f"({late_night['direction']} — 수면 교란 신호)"
        )

    # 5) 외출·일상 앱 비중(active_life) + 수동 소비(passive) — 위축 신호
    act_older = _mean(_daily_group(older_days, ACTIVE_LIFE))
    act_recent = _mean(_daily_group(recent_days, ACTIVE_LIFE))
    pas_recent = _mean(_daily_group(recent_days, PASSIVE))
    act_share_o = act_older / st_older if st_older else 0.0
    act_share_r = act_recent / st_recent if st_recent else 0.0
    pas_share_r = pas_recent / st_recent if st_recent else 0.0
    div_older = _mean(_daily_diversity(older_days))
    div_recent = _mean(_daily_diversity(recent_days))
    active_life = {
        "share_older_pct": round(act_share_o * 100, 1),
        "share_recent_pct": round(act_share_r * 100, 1),
        "passive_recent_pct": round(pas_share_r * 100, 1),
    }
    app_diversity = {
        "older": round(div_older, 1),
        "recent": round(div_recent, 1),
        "direction": _direction(div_recent - div_older, 0.5),
    }
    active_dropped = (
        act_share_o - act_share_r
    ) >= _ACTIVE_DROP and div_recent < div_older
    if active_dropped:
        sev = 2 if (act_share_o - act_share_r) >= 2 * _ACTIVE_DROP else 1
        findings.append(
            {"code": "withdrawal", "bucket": "withdrawing", "severity": sev}
        )
        evidence.append(
            f"외출·일상 앱 비중 {active_life['share_older_pct']}%→{active_life['share_recent_pct']}% "
            f"(감소 — 행동 반경 축소 신호)"
        )
        evidence.append(
            f"앱 다양성 {app_diversity['older']}→{app_diversity['recent']}종 (감소)"
        )
    if pas_share_r >= _PASSIVE_HIGH:
        findings.append({"code": "passive_use", "bucket": "withdrawing", "severity": 1})
        evidence.append(
            f"수동 소비(영상·SNS·게임) 비중 {active_life['passive_recent_pct']}% — 도피적 사용 가능"
        )

    # 6) 카테고리 급증(spike) — 평소 대비 최근 배수
    older_cat = _cat_minutes(older_days)
    recent_cat = _cat_minutes(recent_days)
    n_o, n_r = len(older_days), len(recent_days)
    spikes: list[dict[str, Any]] = []
    for cat in sorted(recent_cat):
        if cat == CAT_OTHER:
            continue
        base = older_cat.get(cat, 0.0) / n_o  # 평소 일평균(분)
        cur = recent_cat[cat] / n_r  # 최근 일평균(분)
        if cur < _SPIKE_MIN_MINUTES:
            continue
        ratio = (cur / base) if base > 0 else float("inf")
        if ratio >= _SPIKE_RATIO:
            spikes.append(
                {
                    "category": cat,
                    "label": CATEGORY_LABEL.get(cat, cat),
                    "baseline": round(base, 1),
                    "recent": round(cur, 1),
                    "ratio": (round(ratio, 1) if base > 0 else None),
                }
            )
            sev = 2 if (base > 0 and ratio >= 5) else 1
            findings.append({"code": "spike", "bucket": "spike", "severity": sev})
            times = f"평소의 {round(ratio, 1)}배" if base > 0 else "새로 급증"
            evidence.append(
                f"{CATEGORY_LABEL.get(cat, cat)} 사용 {round(base, 1)}→{round(cur, 1)}분 ({times})"
            )

    # 7) 취침 추세 — sleep_records.bedtime 우선, 없으면 by_hour 마지막 활동 추정
    sleeps = [s for s in sleep_records if _parse_day(s.get("date")) in set(days)]
    bedtime_by_day: dict[date, float] = {}
    for s in sleeps:
        d = _parse_day(s.get("date"))
        bt = _bedtime_to_minutes(s.get("bedtime")) if s.get("bedtime") else None
        if d is not None and bt is not None:
            bedtime_by_day[d] = bt
    bedtime_source = "sleep_record"
    if not bedtime_by_day and per_day_lastact:  # fallback: 마지막 활동 시각(분)
        bedtime_by_day = {d: per_day_lastact[d] * 60 for d in per_day_lastact}
        bedtime_source = "last_activity_estimate"
    bedtime: Optional[dict[str, Any]] = None
    bt_older_vals = [bedtime_by_day[d] for d in older_days if d in bedtime_by_day]
    bt_recent_vals = [bedtime_by_day[d] for d in recent_days if d in bedtime_by_day]
    if bt_older_vals and bt_recent_vals:
        bt_o, bt_r = _mean(bt_older_vals), _mean(bt_recent_vals)
        bedtime = {
            "older": _minutes_to_clock(bt_o),
            "recent": _minutes_to_clock(bt_r),
            "delta_min": round(bt_r - bt_o, 1),
            "direction": (
                "늦어짐"
                if bt_r - bt_o > _BEDTIME_LATER
                else "빨라짐" if bt_r - bt_o < -_BEDTIME_LATER else "유지"
            ),
            "source": bedtime_source,
        }
        if bt_r - bt_o > _BEDTIME_LATER:
            sev = 2 if bt_r - bt_o > 2 * _BEDTIME_LATER else 1
            findings.append(
                {"code": "bedtime_drift", "bucket": "disrupted", "severity": sev}
            )
            evidence.append(
                f"평균 취침 추정 {bedtime['older']}→{bedtime['recent']} "
                f"(늦어짐 — 생활 리듬 악화 신호)"
            )

    # 8) 수면점수 연계(있으면)
    sleep_link: Optional[dict[str, Any]] = None
    scores = [
        float(s["sleep_score"])
        for s in sleeps
        if s.get("sleep_score") is not None
        and _parse_day(s.get("date")) in set(recent_days)
    ]
    if scores:
        avg_score = round(_mean(scores), 1)
        sleep_link = {
            "avg_sleep_score": avg_score,
            "late_night_minutes_recent": round(ln_recent, 1),
        }
        if avg_score < 60 and ln_recent >= _LATE_NIGHT_WATCH:
            findings.append({"code": "sleep_low", "bucket": "disrupted", "severity": 1})
            evidence.append(
                f"수면점수 평균 {avg_score}점 + 심야 사용 {round(ln_recent, 1)}분 "
                f"— 취침 전 스마트폰 과사용 가설"
            )

    # 9) 카테고리 비중(최근) — 익명화된 표시지표
    recent_total = sum(recent_cat.values()) or 1.0
    category_mix = {
        c: round(m / recent_total * 100, 1)
        for c, m in sorted(recent_cat.items(), key=lambda kv: -kv[1])
        if c != CAT_OTHER and m > 0
    }

    # 10) 헤드라인 신호 — 가장 심각한 finding 기준, 동률은 우선순위로.
    signal, concern = _headline(findings)
    modifier = -1 if signal in (SIGNAL_WITHDRAWING, SIGNAL_DISRUPTED) else 0
    reason = {
        SIGNAL_STABLE: "일상 리듬이 크게 흔들리지 않고 유지되고 있어요.",
        SIGNAL_WITHDRAWING: "바깥·일상 활동이 줄고 화면 안에 머무는 시간이 늘었어요. 더 세심한 돌봄이 필요해요.",
        SIGNAL_DISRUPTED: "밤늦은 사용이 늘며 생활 리듬이 흔들리고 있어요.",
        SIGNAL_SPIKE: "특정 앱 사용이 평소보다 크게 늘었어요. 마음이 분주하거나 무언가 있었을 수 있어요.",
    }[signal]
    if not findings:
        evidence.append("뚜렷한 행동 변화 신호는 보이지 않아요(안정).")

    return {
        "signal": signal,
        "window": {"days": window_days, "as_of": str(as_of) if as_of else None},
        "days_observed": len(days),
        "screen_time": screen_time,
        "late_night": late_night,
        "category_mix": category_mix,
        "active_life": active_life,
        "app_diversity": app_diversity,
        "spikes": spikes,
        "bedtime": bedtime,
        "sleep_link": sleep_link,
        "findings": findings,
        "evidence": evidence,
        "reason": reason,
        # advisory(0~2). ⚠️ 위기(1393) 자동 트리거 아님 — safety 레이어 참고용.
        "concern_level": concern,
        # 미션 강도 보조 힌트(-1=더 쉬운 미션 권장). 수면 신호와 동일하게 점수엔 미반영.
        "mission_intensity_modifier": modifier,
    }


# 헤드라인 우선순위: 위축 > 리듬 교란 > 급증 (임상적 심각도 순).
_BUCKET_PRIORITY: Final = ["withdrawing", "disrupted", "spike"]
_BUCKET_SIGNAL: Final = {
    "withdrawing": SIGNAL_WITHDRAWING,
    "disrupted": SIGNAL_DISRUPTED,
    "spike": SIGNAL_SPIKE,
}


def _headline(findings: list[dict[str, Any]]) -> tuple[str, int]:
    """findings → (헤드라인 신호, concern_level 0~2). 없으면 안정/0."""
    if not findings:
        return SIGNAL_STABLE, 0
    concern = min(2, max(int(f["severity"]) for f in findings))
    # 버킷별 최고 심각도
    by_bucket: dict[str, int] = {}
    for f in findings:
        b = f["bucket"]
        by_bucket[b] = max(by_bucket.get(b, 0), int(f["severity"]))
    best_sev = max(by_bucket.values())
    for bucket in _BUCKET_PRIORITY:  # 동률이면 우선순위 순
        if by_bucket.get(bucket, 0) == best_sev:
            return _BUCKET_SIGNAL[bucket], concern
    return SIGNAL_STABLE, concern
