"""일상복귀 신호 — 발표용 시뮬레이션 데모.

⚠️ 여기 수치는 **실데이터가 아니라 가상 회복 시나리오**입니다(발표에서 "시뮬레이션"이라
밝힐 것). 실수집(access_logs·재생 이벤트)이 붙으면 같은 함수가 실데이터로 동작합니다.

보여주려는 이야기(피드백): "앱 쓰니 일상복귀 빨라졌다"
    초기: 감정 낮음 + 영상/접속 많음(앱에 의존)
    후기: 감정 오름 + 영상/접속 줄어듦(일상으로 복귀)  ← 의존이 줄어드는 게 회복 신호

실행 (레포 루트에서):
    python -m ai.evaluation.demo_recovery_signal
"""

from __future__ import annotations

import io
import sys

from .recovery_signal import compute_recovery_signal

# Windows 콘솔 한글/이모지 인코딩 우회
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# 8주간 가상 회복 시나리오 (오래된→최근)
_WEEKS = 8
_SCORES = [2, 3, 4, 5, 6, 7, 8, 9]  # 감정 점수: 우상향
_ACCESS = [12, 11, 9, 8, 6, 4, 3, 2]  # 앱 접속: 우하향(의존 ↓)
_PLAYS = [14, 12, 10, 7, 6, 4, 3, 2]  # 영상 재생: 우하향
# 완료율 80% — 완료된 항목에만 completed_at 부여(미완료는 날짜 없음, graceful).
# 2026-06-12 재정의: 꾸준함 25점은 이제 "최근 14일 중 미션 완료한 날 수" 기준.
_MISSION_DONE = (1, 1, 0, 1, 1, 1, 0, 1, 1, 1)
_MISSIONS = [
    {"done": bool(d), **({"completed_at": f"2026-04-{i + 1:02d}"} if d else {})}
    for i, d in enumerate(_MISSION_DONE)
]


def _bar(value: float, scale: float, width: int = 20, ch: str = "█") -> str:
    n = int(round(value / scale * width))
    return ch * max(n, 0)


def main() -> None:
    checkins = [
        {"score": s, "created_at": f"2026-04-{i + 1:02d}"} for i, s in enumerate(_SCORES)
    ]

    print("=" * 60)
    print(" 일상복귀 신호 — 시뮬레이션 (가상 데이터 · 발표용)")
    print("=" * 60)
    print(" 주차  감정(1~10)            앱 접속(회)")
    for i in range(_WEEKS):
        print(
            f"  {i + 1:>2}  {_SCORES[i]:>2} {_bar(_SCORES[i], 10):<20}"
            f"  {_ACCESS[i]:>2} {_bar(_ACCESS[i], 12, 12, '▒')}"
        )
    print("  → 감정은 오르고(█), 앱 접속은 줄어듦(▒) = 일상으로 복귀하는 모습")

    result = compute_recovery_signal(
        checkins, _MISSIONS, access_counts=_ACCESS, play_counts=_PLAYS
    )

    print("\n" + "-" * 60)
    print(f" 신호: 【 {result['signal']} 】   회복지수: {result['recovery_index']}/100")
    print(f" 해석: {result['reason']}")
    print(" 근거:")
    for e in result["evidence"]:
        print(f"   · {e}")
    print("-" * 60)
    print(" ※ 실수집(access_logs·재생 이벤트) 연결 시 같은 함수가 실데이터로 동작")


if __name__ == "__main__":
    main()
