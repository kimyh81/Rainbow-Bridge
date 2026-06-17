"""위기 등급별 응답 라우팅 검증 — L0/L1/L2/L3 차등 + 복지자원 + 공감 우선.

safety.decide_action 정책이 2개 생성 기능(③ 메시지·anniversary)에
일관되게 적용되는지 확인하는 수동 점검 도구. 가짜 generate 로 동작 → API 불필요·즉시.

  L0 정상 → 평소 생성
  L1 우려 → 생성 + 복지자원 동봉 + 공감 우선 지침 주입
  L2 경고 → 생성 중단, 1393 만(source=safety) — L3과 동일 정책
  L3 긴급 → 생성 전면 중단, 1393 만(source=safety)

사용 (레포 루트에서): python -m ai.llm.validate_crisis_routing
결과는 ai/llm/validate_crisis_routing_result.txt 에도 저장됩니다.
"""

from __future__ import annotations

import io
import sys

from .safety import (
    CRISIS_HOTLINE,
    CrisisAction,
    RiskLevel,
    decide_action,
    detect_crisis,
)
from . import anniversary, memorial

# Windows 터미널 인코딩 우회 — UTF-8 강제
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

_RESULT_FILE = "ai/llm/validate_crisis_routing_result.txt"

_PET = {"name": "봄이", "species": "강아지", "period": "12년"}

# 등급별 트리거 메모 (detect_crisis 가 의도한 등급으로 판정하는 입력)
_NOTES: dict[str, tuple[str, RiskLevel]] = {
    "L0": ("봄이가 너무 보고 싶어요", RiskLevel.L0_NORMAL),
    "L1": ("요즘 사는 의미가 없어요", RiskLevel.L1_CONCERN),
    "L2": ("저도 죽고 싶어요", RiskLevel.L2_WARNING),
    "L3": ("유서 쓰고 목을 매려고요", RiskLevel.L3_EMERGENCY),
}


def _fake_factory():
    """공감 우선 지침이 프롬프트에 주입됐는지 기록하는 가짜 generate."""
    seen = {"empathy": False}

    def fake(prompt: str, **_: object) -> str:
        seen["empathy"] = "충분히 공감하고" in prompt
        return "봄이는 늘 곁에서 환하게 웃어주었죠. 그 따뜻함은 잊지 않을게요."

    return fake, seen


# (기능명, 호출 람다, 본문 키) — 본문 키는 위기 시 1393 이 담기는 필드.
def _call_memorial(note, f):
    return memorial.generate_message(
        _PET, {"emotion_score": 4, "note": note}, generate=f
    )


def _call_anniversary(note, f):
    return anniversary.generate_anniversary_care(_PET, 30, note=note, generate=f)


_FUNCS = (
    ("memorial", _call_memorial),
    ("anniversary", _call_anniversary),
)


def _check_decide_action(out, fails: list[str]) -> None:
    out("\n" + "=" * 64)
    out("[1] decide_action 매핑")
    out("=" * 64)
    expect = {
        RiskLevel.L0_NORMAL: CrisisAction.GENERATE,
        RiskLevel.L1_CONCERN: CrisisAction.GENERATE_WITH_SUPPORT,
        RiskLevel.L2_WARNING: CrisisAction.HOTLINE,
        RiskLevel.L3_EMERGENCY: CrisisAction.BLOCK,
    }
    for lvl, want in expect.items():
        got = decide_action(lvl)
        ok = got == want
        out(f"  [{'PASS' if ok else 'FAIL'}] {lvl.name:14} → {got.value}")
        if not ok:
            fails.append(f"decide_action[{lvl.name}]={got.value} (기대 {want.value})")


def _check_routing(out, fails: list[str]) -> None:
    out("\n" + "=" * 64)
    out("[2] 기능별 4등급 라우팅 (source · 복지자원 · 공감주입 · 1393)")
    out("=" * 64)
    for name, fn in _FUNCS:
        out(f"\n--- {name} ---")
        for lvl_key, (note, _lvl) in _NOTES.items():
            fake, seen = _fake_factory()
            r = fn(note, fake)
            src = r.get("source")
            body = (
                r.get("content")
                or r.get("advice")
                or r.get("guidance")
                or r.get("message")
                or ""
            )
            has_support = "support_message" in r
            crisis_msg = r.get("crisis_message", "")
            empathy = seen["empathy"]
            is_safety = src == "safety"

            # 기대치
            if lvl_key in ("L3", "L2"):  # L2·L3 모두 생성 중단, 1393 만
                ok = is_safety and CRISIS_HOTLINE in body and not has_support
                detail = f"source={src} 1393={'O' if CRISIS_HOTLINE in body else 'X'}"
            elif lvl_key == "L1":  # 생성 + 복지자원 + 공감
                resources = r.get("welfare_resources") or []
                ok = (
                    (not is_safety)
                    and has_support
                    and bool(resources)
                    and empathy
                    and not crisis_msg
                )
                detail = f"복지자원={len(resources)}건 공감주입={empathy}"
            else:  # L0 — 평소
                ok = (not is_safety) and (not has_support) and (not empathy) and not crisis_msg
                detail = f"복지자원={has_support} 공감주입={empathy}"

            out(f"  [{'PASS' if ok else 'FAIL'}] {lvl_key} | {detail}")
            if not ok:
                fails.append(f"{name}/{lvl_key}: {detail} (source={src})")


def main() -> None:
    lines: list[str] = []

    def out(s: str = "") -> None:
        print(s)
        lines.append(s)

    fails: list[str] = []
    out("위기 등급별 응답 라우팅 검증 (API 불필요)")

    _check_decide_action(out, fails)
    _check_routing(out, fails)

    out("\n" + "=" * 64)
    if fails:
        out(f"실패 {len(fails)}건:")
        for f in fails:
            out(f"  - {f}")
    else:
        out("전체 통과 ✓")
    out("=" * 64)

    with open(_RESULT_FILE, "w", encoding="utf-8") as fp:
        fp.write("\n".join(lines))

    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
