"""발표 시나리오 계정 시드 스크립트

계정별 게이트 상태 (비밀번호: js1234):
  demo00 — locked        (체크인 0)
  demo01 — teaser        (체크인 3, 헬스 2, 미션 10일) score ~45
  demo02 — open          (체크인 4, 헬스 3, 미션 15일) score ~57 — 3인칭 편지·GIF
  demo03 — open+히든미션  (체크인 4, 헬스 3, 미션 15일) — 슬라이드쇼
  demo04 — open+1인칭    (체크인 7, 헬스 7, 미션 24일) score ~82
  demo05 — 예비

실행 (서버에서): cd backend && python scripts/seed_scenario.py
로컬 실행:       cd backend && py -3.13 scripts/seed_scenario.py

※ MongoDB 직접 삽입(미션 과거 날짜)은 서버에서 실행해야 합니다.
  로컬에서 실행하면 MongoDB 연결 실패 시 경고 후 건너뜁니다.

RESET=True 이면 기존 체크인·헬스·미션 데이터를 삭제 후 재시드합니다.
"""

from __future__ import annotations

import os
import time
import random
from datetime import date, datetime, timedelta, timezone
import httpx
from dotenv import load_dotenv

load_dotenv()

BASE = "https://rainbow-bridge.duckdns.org"
PASSWORD = "js1234"

# True 면 기존 체크인·헬스·미션 데이터 삭제 후 재시드 (서버 실행 시 권장)
RESET = True

# 사진 파일 경로 — 실행 전에 실제 파일 경로로 바꾸세요. None 이면 생략.
PET_PHOTO_PATH: str | None = None  # 예) "/home/user/haneuli.jpg"

# MongoDB 직접 연결 설정
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "rainbow_bridge")

# 미션 풀 — 날짜별로 순환 사용
_MISSION_POOL = [
    ("오늘 산책하기", "15분이라도 밖에 나가 바람을 쐬어보세요.", "activity", "small"),
    (
        "소중한 사람에게 연락하기",
        "가까운 가족이나 친구에게 안부를 전해보세요.",
        "connection",
        "small",
    ),
    (
        "반려동물과의 추억 기록하기",
        "소중한 기억을 글이나 사진으로 남겨보세요.",
        "record",
        "small",
    ),
    ("따뜻한 음료 마시기", "잠깐 쉬며 따뜻한 차 한 잔 마셔보세요.", "rest", "gentle"),
    (
        "좋아하는 음악 듣기",
        "마음이 편한 음악을 들으며 잠시 쉬어가세요.",
        "rest",
        "gentle",
    ),
]

ACCOUNTS = [
    {
        "email": "demo00@demo.com",
        "nickname": "김지수",
        "checkins": [],  # 체크인 없음
        "health_days": 0,
        "missions_days": 0,
    },
    {
        "email": "demo01@demo.com",
        "nickname": "김지수",
        "checkins": [6, 7, 8],  # 상향 추세 → 감정추세 점수 ↑
        "health_days": 2,
        "missions_days": 10,
    },
    {
        "email": "demo02@demo.com",
        "nickname": "김지수",
        "checkins": [6, 7, 7, 8],
        "health_days": 3,
        "missions_days": 15,
    },
    {
        "email": "demo03@demo.com",
        "nickname": "김지수",
        "checkins": [5, 6, 6, 7, 7, 8, 9],
        "health_days": 7,
        "missions_days": 24,
        "hidden_mission": True,  # 슬라이드쇼 트리거
    },
    {
        "email": "demo04@demo.com",
        "nickname": "김지수",
        "checkins": [5, 6, 6, 7, 7, 8, 9],
        "health_days": 7,
        "missions_days": 24,
    },
    {
        "email": "demo05@demo.com",
        "nickname": "김지수",
        "checkins": [],
        "health_days": 0,
        "missions_days": 0,
    },
]

PET = {
    "name": "하늘이",
    "species": "강아지",
    "breed": "말티즈",
    "gender": "여아",
    "caller_name": "지수",
    "period": "2019-01-01 ~ 2026-06-01",
    "memories": [
        {
            "keyword": "처음 만난 날",
            "detail": "작고 하얀 솜뭉치 같은 하늘이가 처음 품 안에 안기던 날, 그 온기가 아직도 손바닥에 남아있다",
        },
        {
            "keyword": "좋아하던 산책길",
            "detail": "집 앞 공원 산책길, 매번 처음 보는 것처럼 꼬리를 흔들던 하늘이. 이제 그 길을 혼자 걷는 게 이렇게 긴 줄 몰랐다",
        },
        {
            "keyword": "간식 앞에서 기다리기",
            "detail": "'기다려' 하면 작은 발을 꼭 모으고 눈을 빛내며 얌전히 기다렸다. 그 눈빛이 자꾸 생각난다",
        },
        {
            "keyword": "비 오는 날의 낮잠",
            "detail": "빗소리 들리면 꼭 내 옆에 와서 웅크리고 잠들었다. 이제 비 오는 날 그 자리가 너무 비어있다",
        },
        {
            "keyword": "마지막으로 함께한 아침",
            "detail": "평소처럼 밥 먹고, 평소처럼 햇살 드는 자리에 누웠다. 그게 마지막 아침인 줄 몰랐다",
        },
        {
            "keyword": "이름을 부르면",
            "detail": "하늘아, 하고 부르면 어디서든 달려왔다. 지금도 이름을 부르면 올 것만 같아서 아직 부를 수가 없다",
        },
        {
            "keyword": "아픈 날의 일기",
            "detail": "오늘 하늘이가 밥을 조금 먹었다. 힘들어 보였지만, 내 손을 오래 핥아줬다",
        },
    ],
    "bucket_list": [
        "매일 산책하기",
        "예쁜 사진 많이 찍기",
        "함께 피크닉 가기",
        "맛있는 간식 먹기",
    ],
}


# ── MongoDB 직접 삽입 유틸 ────────────────────────────────────────────────────


def _mongo_col(name: str):
    from pymongo import MongoClient

    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    return client, client[MONGO_DB_NAME][name]


def _reset_pet_data(pet_id: str):
    """기존 체크인·헬스·미션 데이터 삭제 + pet memories/bucket_list 갱신."""
    try:
        from bson import ObjectId

        client, _ = _mongo_col("emotions")
        db = client[MONGO_DB_NAME]
        r1 = db["emotions"].delete_many({"pet_id": pet_id})
        r2 = db["missions"].delete_many({"pet_id": pet_id})
        r3 = db["health_logs"].delete_many({"pet_id": pet_id})
        r4 = db["usage_stats"].delete_many({"pet_id": pet_id})
        try:
            db["pets"].update_one(
                {"_id": ObjectId(pet_id)},
                {
                    "$set": {
                        "memories": PET["memories"],
                        "bucket_list": PET["bucket_list"],
                    }
                },
            )
            print("  pet memories/bucket_list 갱신 완료")
        except Exception:
            pass
        print(
            f"  RESET: 감정 {r1.deleted_count}·미션 {r2.deleted_count}·헬스 {r3.deleted_count}·사용량 {r4.deleted_count} 삭제"
        )
        client.close()
    except Exception as e:
        print(f"  RESET 실패: {e.__class__.__name__} — 기존 데이터 위에 추가됩니다")


def _insert_missions_mongo(pet_id: str, days: int):
    """MongoDB에 과거 days일치 미션 완료 레코드 직접 삽입."""
    try:
        client, col = _mongo_col("missions")
        today = datetime.now(timezone.utc).replace(
            hour=12, minute=0, second=0, microsecond=0
        )
        for i in range(days):
            past = today - timedelta(days=i + 1)
            m = _MISSION_POOL[i % len(_MISSION_POOL)]
            col.insert_one(
                {
                    "pet_id": pet_id,
                    "title": m[0],
                    "description": m[1],
                    "category": m[2],
                    "rationale": None,
                    "difficulty": m[3],
                    "completed": True,
                    "skipped": False,
                    "created_at": past,
                    "completed_at": past,
                }
            )
        client.close()
        print(f"  MongoDB: 과거 {days}일치 미션 삽입")
        return True
    except Exception as e:
        print(f"  MongoDB 미션 삽입 실패: {e.__class__.__name__} — 서버에서 실행하세요")
        return False


# ── API 헬퍼 ─────────────────────────────────────────────────────────────────


def register_and_login(c: httpx.Client, email: str, nickname: str) -> str | None:
    r = c.post(
        "/api/v1/auth/register",
        json={"email": email, "password": PASSWORD, "nickname": nickname},
    )
    if r.status_code not in (200, 201, 409):
        print(f"  회원가입 실패: {r.status_code} {r.text[:100]}")
    r = c.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    if r.status_code != 200:
        print(f"  로그인 실패: {r.status_code} {r.text}")
        return None
    return r.json()["access_token"]


def get_or_create_pet(c: httpx.Client, headers: dict) -> str | None:
    pets = c.get("/api/v1/pets", headers=headers).json()
    if pets:
        return pets[0]["id"]
    r = c.post("/api/v1/pets", json=PET, headers=headers)
    if r.status_code == 201:
        pet_id = r.json()["id"]
        c.patch(f"/api/v1/pets/{pet_id}/memorial", headers=headers)
        print("  memorial_mode 활성화")
        if PET_PHOTO_PATH:
            with open(PET_PHOTO_PATH, "rb") as f:
                fname = PET_PHOTO_PATH.replace("\\", "/").split("/")[-1]
                pr = c.post(
                    f"/api/v1/pets/{pet_id}/photo",
                    files={"file": (fname, f, "image/jpeg")},
                    headers=headers,
                )
            if pr.status_code == 200:
                print(f"  사진 업로드 완료: {pr.json().get('photo_url','')[:60]}")
            else:
                print(f"  사진 업로드 실패: {pr.status_code} {pr.text[:80]}")
        return pet_id
    print(f"  펫 등록 실패: {r.status_code} {r.text}")
    return None


def seed_checkins(c: httpx.Client, headers: dict, pet_id: str, scores: list[int]):
    """감정 체크인 — scores 리스트 순서대로 입력 (상향 추세면 올라가는 순서)."""
    for i, score in enumerate(scores):
        r = c.post(
            "/api/v1/emotions",
            json={"pet_id": pet_id, "score": score, "note": "오늘 하루 잘 버텼어요"},
            headers=headers,
        )
        risk = (
            r.json().get("risk_level", "?")
            if r.status_code == 201
            else f"err({r.status_code})"
        )
        print(f"  체크인 {i+1}: score={score} risk={risk}")
        time.sleep(1.0)


def seed_health(c: httpx.Client, headers: dict, pet_id: str, days: int):
    if days == 0:
        return
    today = date.today()
    for i in range(days):
        d = (today - timedelta(days=i)).isoformat()
        steps = random.randint(5000, 9000)
        sleep_h = round(random.uniform(6.0, 7.5), 1)
        start = f"{d}T08:00:00+09:00"
        end = f"{d}T08:10:00+09:00"
        sleep_start = f"{d}T00:00:00+09:00"
        sleep_end = f"{d}T{int(sleep_h):02d}:{int((sleep_h % 1) * 60):02d}:00+09:00"
        c.post(
            "/api/v1/health/sync",
            json={
                "pet_id": pet_id,
                "steps_result": {
                    "records": [{"count": steps, "startTime": start, "endTime": end}]
                },
                "sleep_result": {
                    "records": [
                        {"startTime": sleep_start, "endTime": sleep_end, "stages": []}
                    ]
                },
            },
            headers=headers,
        )
        late = random.randint(5, 20)  # 야간 폰 사용 적게 (생활패턴 점수 ↑)
        c.post(
            "/api/v1/usage-stats",
            json=[
                {
                    "date": d,
                    "category": "SNS",
                    "minutes": random.randint(20, 60),
                    "late_night_minutes": late,
                }
            ],
            headers=headers,
        )
        print(f"  헬스 {d}: {steps}보 / 수면 {sleep_h}h / 야간폰 {late}분")
        time.sleep(0.2)


def seed_hidden_mission(c: httpx.Client, headers: dict, pet_id: str, base_days: int):
    """demo03 전용 — 과거 미션 + 슬라이드쇼 트리거.

    base_days일치 과거 미션을 MongoDB에 삽입하고,
    오늘 미션 1개를 API로 완료해서 슬라이드쇼를 트리거합니다.
    """
    ok = _insert_missions_mongo(pet_id, base_days)
    if not ok:
        print("  히든미션: MongoDB 연결 불가 — 서버에서 실행 필요")
        return

    # 오늘 미션 API 완료 → completed_days >= 2 → 슬라이드쇼 트리거
    r = c.get(f"/api/v1/missions/{pet_id}", headers=headers)
    missions = r.json() if r.status_code == 200 else []
    for m in missions:
        mid = m.get("id") or m.get("_id")
        if not mid or m.get("completed"):
            continue
        cr = c.patch(
            f"/api/v1/missions/{mid}/complete",
            json={"completed": True},
            headers=headers,
        )
        if cr.status_code == 200:
            print("  히든미션: 오늘 미션 완료 → 슬라이드쇼 트리거")
            break


# ── 메인 ─────────────────────────────────────────────────────────────────────

with httpx.Client(base_url=BASE, timeout=90) as c:
    for acc in ACCOUNTS:
        print(f"\n── {acc['email']} ──")
        token = register_and_login(c, acc["email"], acc["nickname"])
        if not token:
            continue
        headers = {"Authorization": f"Bearer {token}"}

        pet_id = get_or_create_pet(c, headers)
        if not pet_id:
            continue
        print(f"  펫: {pet_id}")

        if RESET:
            _reset_pet_data(pet_id)

        seed_checkins(c, headers, pet_id, acc["checkins"])
        seed_health(c, headers, pet_id, acc["health_days"])

        if acc.get("hidden_mission"):
            seed_hidden_mission(c, headers, pet_id, acc["missions_days"])
        elif acc["missions_days"] > 0:
            _insert_missions_mongo(pet_id, acc["missions_days"])

        r = c.get(f"/api/v1/emotions/recovery/{pet_id}", headers=headers)
        d = r.json()
        print(
            f"  → gate={d.get('gate_status')} score={d.get('recovery_pct')} "
            f"content={d.get('content_unlocked')} allow_1st={d.get('allow_first_person')}"
        )

print("\n완료")
