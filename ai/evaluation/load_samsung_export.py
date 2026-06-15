"""삼성헬스 export(zip) → ``health_logs`` 적재 — A 경로(폰·개발빌드 없이 발표용 실데이터).

[health_export_adapter.py](health_export_adapter.py) 로 파싱한 ``{steps, sleep_hours}`` 를
``GET /report`` 가 읽는 health_logs 문서로 만들어 넣는다. 문서 모양은
``POST /health/sync`` 엔드포인트와 **동일**:

    {"pet_id": ..., "date": "YYYY-MM-DD", "steps": int|None,
     "sleep_hours": float|None, "synced_at": <UTC datetime>}

기본은 **출력만**(안전). 실제 DB 적재는 ``--write`` 를 줄 때만, 대상 URI 를 크게 찍고 한다.

⚠️ 두 가지 꼭 기억:
  1) ``GET /report`` 는 health_logs 에서 **(pet_id 기준) 가장 최근 date 한 건**만 읽는다
     (`report.py` `find_one(sort=[("date",-1)])`). 발표 백엔드(NCP)에 보이게 하려면
     **그 NCP 의 mongo** 에 ``--write`` 하고, 이 문서가 최신 날짜인지 확인할 것
     (필요하면 ``--date`` 로 강제). 로컬 27017 에 넣으면 NCP 리포트엔 안 나온다.
  2) 실 export 는 걸음은 최근까지, 수면은 거의 없음(측정 안 함) → 최근 날짜는 보통
     **걸음만 있고 ``sleep_hours=None``**. 정상이다. 수면-감정 교차검증 데모는
     실데이터가 아니라 시뮬레이션(`demo_health_report.py`) 으로 보여줄 것.

실행 (레포 루트에서):
    # 1) 무엇이 들어갈지 확인만 (DB 안 건드림)
    python -m ai.evaluation.load_samsung_export <export.zip> --pet-id <PET_ID>

    # 2) 특정 날짜로 강제(리포트 최신으로 띄우기)
    python -m ai.evaluation.load_samsung_export <export.zip> --pet-id <ID> --date 2025-09-17

    # 3) 실제 적재 (대상 mongo 지정 — NCP 면 그 URI)
    python -m ai.evaluation.load_samsung_export <export.zip> --pet-id <ID> \
        --write --mongo-uri "mongodb://<host>:27017" --db rainbow_bridge
"""

from __future__ import annotations

import argparse
import json
import sys
import zipfile
from datetime import datetime, timezone
from typing import Optional

try:  # 패키지 실행(-m) ↔ 단독/테스트 임포트 양쪽 지원
    from .health_export_adapter import available_step_dates, from_samsung_export
except ImportError:  # pragma: no cover
    from health_export_adapter import available_step_dates, from_samsung_export


# ── export zip 안에서 걸음·수면 CSV 고르기 ──────────────────────────────────
def _pick_member(
    names: list[str], must_have: list[str], must_not: tuple[str, ...] = ()
):
    for n in names:
        low = n.lower()
        if (
            low.endswith(".csv")
            and all(m in low for m in must_have)
            and not any(x in low for x in must_not)
        ):
            return n
    return None


def read_export_zip(zip_path: str) -> tuple[Optional[str], Optional[str]]:
    """export zip → (걸음 CSV 텍스트, 수면 CSV 텍스트). 못 찾은 쪽은 None.

    걸음 = ``com.samsung.shealth.step_daily_trend.*.csv``
    수면 = ``com.samsung.shealth.sleep.*.csv``  (sleep_stage 는 제외)
    """
    with zipfile.ZipFile(zip_path) as z:
        names = z.namelist()
        step_name = _pick_member(names, ["step_daily_trend"])
        sleep_name = _pick_member(names, ["shealth.sleep."], must_not=("sleep_stage",))
        steps_csv = (
            z.read(step_name).decode("utf-8-sig", errors="replace")
            if step_name
            else None
        )
        sleep_csv = (
            z.read(sleep_name).decode("utf-8-sig", errors="replace")
            if sleep_name
            else None
        )
    return steps_csv, sleep_csv


def _read_text(path: str) -> str:
    with open(path, encoding="utf-8-sig", errors="replace") as f:
        return f.read()


def build_health_log_doc(
    *, pet_id: str, date: str, steps: Optional[int], sleep_hours: Optional[float]
) -> dict:
    """health_logs 적재용 문서. POST /health/sync 가 만드는 모양과 동일."""
    return {
        "pet_id": pet_id,
        "date": date,
        "steps": steps,
        "sleep_hours": sleep_hours,
        "synced_at": datetime.now(timezone.utc),
        "source": "samsung_export",  # 동기화 경로 구분용(엔드포인트엔 없는 표식)
    }


def _resolve_csvs(args) -> tuple[Optional[str], Optional[str]]:
    """--steps-csv/--sleep-csv 직접 지정이 있으면 우선, 없으면 zip 에서 추출."""
    steps_csv = _read_text(args.steps_csv) if args.steps_csv else None
    sleep_csv = _read_text(args.sleep_csv) if args.sleep_csv else None
    if (steps_csv is None or sleep_csv is None) and args.zip_path:
        z_steps, z_sleep = read_export_zip(args.zip_path)
        steps_csv = steps_csv or z_steps
        sleep_csv = sleep_csv or z_sleep
    return steps_csv, sleep_csv


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(
        description="삼성헬스 export → health_logs 적재 (A 경로)"
    )
    p.add_argument("zip_path", nargs="?", help="samsunghealth_*.zip 경로")
    p.add_argument("--pet-id", required=True, help="대상 반려동물 id")
    p.add_argument(
        "--date",
        help="적재할 날짜(YYYY-MM-DD). 생략 시 걸음 데이터의 최근일.",
    )
    p.add_argument("--steps-csv", help="걸음 CSV 직접 지정(zip 대신)")
    p.add_argument("--sleep-csv", help="수면 CSV 직접 지정(zip 대신)")
    p.add_argument(
        "--write", action="store_true", help="실제 mongo 적재(미지정 시 출력만)"
    )
    p.add_argument(
        "--mongo-uri", default="mongodb://localhost:27017", help="대상 mongo URI"
    )
    p.add_argument("--db", default="rainbow_bridge", help="DB 이름")
    p.add_argument("--collection", default="health_logs", help="컬렉션 이름")
    args = p.parse_args(argv)

    try:
        sys.stdout.reconfigure(encoding="utf-8")  # Windows 콘솔 한글
    except Exception:
        pass

    if not args.zip_path and not (args.steps_csv or args.sleep_csv):
        p.error("zip_path 또는 --steps-csv/--sleep-csv 중 하나는 필요합니다.")

    steps_csv, sleep_csv = _resolve_csvs(args)
    if steps_csv is None and sleep_csv is None:
        print("❌ zip 에서 걸음/수면 CSV 를 찾지 못했습니다.")
        return 1

    # 날짜 결정 — 지정 없으면 걸음 데이터의 최근일
    date = args.date
    if date is None:
        dates = available_step_dates(steps_csv) if steps_csv else []
        if not dates:
            print(
                "❌ 걸음 데이터에서 날짜를 찾지 못했습니다. --date 로 직접 지정하세요."
            )
            return 1
        date = dates[-1]
        print(
            f"ℹ️  --date 미지정 → 걸음 데이터 최근일 사용: {date} (전체 {len(dates)}일)"
        )

    parsed = from_samsung_export(steps_csv, sleep_csv, date=date)
    doc = build_health_log_doc(pet_id=args.pet_id, date=date, **parsed)

    print("\n적재할 문서:")
    print(json.dumps(doc, ensure_ascii=False, indent=2, default=str))
    if parsed.get("sleep_hours") is None:
        print(
            "ℹ️  이 날짜엔 수면 데이터 없음(sleep_hours=None) — 걸음만 반영. "
            "실 export 는 보통 수면 기록이 거의 없어 정상입니다."
        )

    if not args.write:
        print(
            "\n(출력만) 실제 적재하려면 --write 와 --mongo-uri 를 주세요. "
            "발표 리포트에 보이려면 그 백엔드(NCP)의 mongo 여야 합니다."
        )
        return 0

    # ── 실제 적재 — 대상 URI 를 크게 찍고 ──
    from pymongo import MongoClient

    print(
        f"\n⚠️  WRITE 모드 — 대상 MongoDB: {args.mongo_uri}  "
        f"DB={args.db}  컬렉션={args.collection}"
    )
    if args.date:
        print(
            f"   ⚠️  --date {args.date} 로 강제 — 같은 pet_id·날짜의 실 sync 문서가 있으면 덮어씁니다."
        )
    # URI 오타 시 30s 행 방지 — 빠르게 실패
    client = MongoClient(args.mongo_uri, serverSelectionTimeoutMS=5000)
    try:
        coll = client[args.db][args.collection]
        res = coll.update_one(
            {"pet_id": doc["pet_id"], "date": doc["date"]},
            {"$set": doc},
            upsert=True,
        )
        action = (
            "신규 삽입"
            if res.upserted_id
            else f"기존 갱신(matched={res.matched_count})"
        )
        print(f"   ✅ upsert 완료 — {action}")
        print(
            f"   GET /report?pet_id={doc['pet_id']} 가 (이 날짜가 최신이면) "
            "이 값을 회복점수에 반영합니다."
        )
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
