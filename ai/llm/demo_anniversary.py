"""기념일 케어(anniversary) 엔진 데모 — 실제 함수 호출 결과 출력.

백엔드/프론트 미연결 상태라, AI 엔진(ai/llm/anniversary.py)을 직접 호출해 동작을 확인합니다.
- check_anniversary / 템플릿 경로 / 위기 분기는 실제 로직 그대로(LLM 불필요).
- note(감정 메모) 경로는 Gemini 대신 가짜 generate를 주입해 흐름만 시연.

실행: python ai/llm/demo_anniversary.py
"""

import json
import sys
from datetime import date

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")  # Windows 콘솔(cp949) 한글 출력 대비

from ai.llm.anniversary import check_anniversary, generate_anniversary_care

LINE = "=" * 72


def stub_generate(prompt, *, max_tokens=350, temperature=0.6, json_mode=False):
    """실제 Gemini 대신 — note 경로 흐름 시연용 가짜 응답."""
    return (
        "푸딩이가 떠난 지도 한 달이 되었네요. 텅 빈 자리가 여전히 크게 느껴지시는 게 "
        "당연합니다. 그 빈자리만큼 깊이 사랑하셨다는 뜻이니까요. 오늘은 푸딩이가 좋아하던 "
        "창가에 잠시 앉아 햇살을 함께 느껴보시는 건 어떨까요. 천천히, 보호자님의 속도로 "
        "걸어가셔도 괜찮습니다."
    )


pet = {"name": "푸딩", "species": "강아지", "memories": ["창가에서 햇살 쬐기", "함께한 산책"]}
passed = date(2026, 5, 13)  # 무지개다리 건넌 날

print(LINE)
print("1) check_anniversary — 오늘이 트리거 날(D+30 / D+100 / D+365)인지 판단")
print(LINE)
for today in [
    date(2026, 6, 12),   # D+30  → 30
    date(2026, 8, 21),   # D+100 → 100
    date(2026, 6, 1),    # D+19  → None
    date(2027, 5, 13),   # D+365 → 365 (1주기)
]:
    d = (today - passed).days
    print(f"  떠난날 {passed} / 오늘 {today} (D+{d}) → check_anniversary = {check_anniversary(passed, today)}")
print("\n  ※ 현재 트리거: D+30, D+100, D+365(1주기). (그 외 모든 날 None)")

print()
print(LINE)
print("2) note 없음 → 고정 템플릿 (LLM 호출 없음, 실제 출력) · 이름 받침별 조사 확인")
print(LINE)
for name in ("푸딩", "코코"):  # 푸딩=받침 있음 / 코코=받침 없음
    for d in (30, 100, 365):
        r = generate_anniversary_care({"name": name, "species": "강아지"}, d, generate=stub_generate)
        print(f"\n[{name} · D+{d} · {r['milestone_label']} · source={r['source']}]")
        print(r["message"])

print()
print(LINE)
print("3) note 있음 → 감정 맞춤 생성 (여기선 가짜 LLM 주입)")
print(LINE)
r = generate_anniversary_care(
    pet, 30, note="요즘 자꾸 푸딩이 생각에 눈물이 나요.", generate=stub_generate
)
print(f"[source={r['source']} · risk_level={r.get('risk_level')}]")
print(r["message"])

print()
print(LINE)
print("4) note에 위기 신호 → 1393 우선 분기 (안전 로직, 실제)")
print(LINE)
r = generate_anniversary_care(
    pet, 100, note="푸딩이 없으니 나도 따라가고 싶어. 더는 살고 싶지 않아.", generate=stub_generate
)
print(json.dumps(r, ensure_ascii=False, indent=2))
