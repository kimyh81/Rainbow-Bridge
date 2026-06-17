"""데모 계정 완전 삭제 스크립트

서버에서 실행:
    cd /app/backend && python scripts/nuke_demo.py

삭제 범위:
  - SQLite users (demo00~05)
  - MongoDB: pets, messages, emotions, missions,
             health_logs, media, usage_stats
"""

from __future__ import annotations

import os
import sqlite3

from dotenv import load_dotenv

load_dotenv()

DEMO_EMAILS = [f"demo{i:02d}@demo.com" for i in range(6)]

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "rainbow_bridge")

# SQLite 경로 — 환경변수 우선, 없으면 두 경로 순서대로 시도
_SQLITE_CANDIDATES = [
    os.getenv("SQLITE_DB_PATH", ""),
    "/app/backend/data/rainbow_bridge.db",
    "/app/backend/rainbow_bridge.db",
    "data/rainbow_bridge.db",
    "rainbow_bridge.db",
]
SQLITE_PATH = next((p for p in _SQLITE_CANDIDATES if p and os.path.exists(p)), None)


# ── SQLite ───────────────────────────────────────────────────────────────────


def nuke_sqlite() -> list[str]:
    """demo 계정 삭제 → 삭제된 user_id 목록 반환."""
    if not SQLITE_PATH:
        print(
            "[SQLite] DB 파일을 찾지 못했습니다. SQLITE_DB_PATH 환경변수를 확인하세요."
        )
        return []

    print(f"[SQLite] 경로: {SQLITE_PATH}")
    conn = sqlite3.connect(SQLITE_PATH)
    cur = conn.cursor()

    ph = ",".join("?" * len(DEMO_EMAILS))
    cur.execute(f"SELECT id, email FROM users WHERE email IN ({ph})", DEMO_EMAILS)
    rows = cur.fetchall()
    if not rows:
        print("[SQLite] demo 계정 없음 (이미 삭제됐거나 다른 경로)")
        conn.close()
        return []

    user_ids = [str(r[0]) for r in rows]
    for uid, email in rows:
        print(f"  삭제 예정: {uid}  {email}")

    cur.execute(
        f"DELETE FROM users WHERE id IN ({','.join('?' * len(user_ids))})", user_ids
    )
    conn.commit()
    conn.close()
    print(f"[SQLite] {len(user_ids)}개 계정 삭제 완료")
    return user_ids


# ── MongoDB ──────────────────────────────────────────────────────────────────


def nuke_mongo(user_ids: list[str]):
    try:
        from pymongo import MongoClient
    except ImportError:
        print("[MongoDB] pymongo 없음 — pip install pymongo")
        return

    try:
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        db = client[MONGO_DB_NAME]
        client.admin.command("ping")
    except Exception as e:
        print(f"[MongoDB] 연결 실패: {e}")
        return

    # user_id로 pets 조회
    query = {"user_id": {"$in": user_ids}} if user_ids else {}
    pets = list(db["pets"].find(query, {"_id": 1, "name": 1}))
    pet_ids = [str(p["_id"]) for p in pets]

    if not pets:
        # user_ids 없거나 pets가 없을 때 — email 패턴 기반으로 직접 조회 불가
        # → 수동 확인 필요
        print("[MongoDB] pets 없음. user_ids:", user_ids or "없음")
        client.close()
        return

    print(f"\n[MongoDB] 삭제 대상 pets: {len(pets)}개")
    for p in pets:
        print(f"  {p['_id']}  {p.get('name', '?')}")

    # pets 삭제
    r = db["pets"].delete_many({"_id": {"$in": [p["_id"] for p in pets]}})
    print(f"  pets: {r.deleted_count}건 삭제")

    # pet_id 기반 컬렉션 삭제
    COLS = ["messages", "emotions", "missions", "health_logs", "media", "usage_stats"]
    for col in COLS:
        r = db[col].delete_many({"pet_id": {"$in": pet_ids}})
        if r.deleted_count:
            print(f"  {col}: {r.deleted_count}건 삭제")

    client.close()
    print("[MongoDB] 완료")


# ── main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 52)
    print("  DEMO 계정 완전 삭제")
    print(f"  대상: {', '.join(DEMO_EMAILS)}")
    print("=" * 52)

    user_ids = nuke_sqlite()
    nuke_mongo(user_ids)

    print("\n[완료] seed_scenario.py 로 재시드하세요.")
    print("  cd /app/backend && python scripts/seed_scenario.py")
