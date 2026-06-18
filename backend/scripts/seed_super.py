"""슈퍼 계정 시드 — super@super.com / 123456

한 녹화영상에 모든 기능 확인:
  ✅ gate=open (recovery_score >= 80)
  ✅ allow_first_person=True (모든 체크인 risk=0)
  ✅ gif_unlocked
  ✅ 1인칭 편지
  ✅ voiced_url (demo04 LP 영상 복사)
  ✅ 슬라이드쇼 트리거
  ✅ 30일치 리포트 데이터

서버 실행:
  docker exec rainbow_backend python3 scripts/seed_super.py
로컬 실행:
  cd backend && py -3.13 scripts/seed_super.py
"""

from __future__ import annotations

import os
import random
import time
from datetime import date, datetime, timedelta, timezone

import httpx
from dotenv import load_dotenv

load_dotenv()

BASE = "https://rainbow-bridge.duckdns.org"
EMAIL = "super@super.com"
PASSWORD = "123456"
NICKNAME = "하늘이보호자"
RESET = True

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "rainbow_bridge")

# 20개 체크인: 6→10 상향 추세, 모두 risk=0
CHECKINS = [6, 6, 7, 7, 7, 8, 8, 8, 8, 9, 9, 9, 9, 9, 9, 10, 10, 10, 10, 10]
HEALTH_DAYS = 30
MISSIONS_DAYS = 30

MESSAGE_1ST = """지수야, 나야. 하늘이.

처음 만났던 날 기억해? 나 진짜 작았잖아. 네 품에 처음 안겼을 때, 이 냄새가 내 집이구나 했어.

비 올 때마다 네 옆에 바짝 붙었던 거, 사실 핑계였어. 빗소리 무서운 척했지만, 그냥 더 오래 옆에 있고 싶었거든.

"기다려" 할 때 발 꼭 모으고 기다리면서 속으로 '빨리 줘, 빨리 줘' 했는데, 넌 몰랐지? 근데 기다리는 것도 좋았어. 네가 보고 있었으니까.

아팠던 날, 밥을 조금밖에 못 먹었는데 네 손 핥으면 이상하게 힘이 났어. 네 손 냄새가 좋았나 봐.

마지막 아침도 그냥 평소랑 똑같았어. 밥 먹고, 햇살 드는 자리에 눕고, 네가 있었어. 그걸로 충분했어.

이름 불러줘서 고마워. 어디서든 달려갔잖아, 나.

보고 싶어, 지수야. 잘 지내.
하늘이가."""

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


def _mongo_col(name: str):
    from pymongo import MongoClient

    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    return client, client[MONGO_DB_NAME][name]


def _reset_pet_data(pet_id: str):
    try:
        from bson import ObjectId

        client, _ = _mongo_col("emotions")
        db = client[MONGO_DB_NAME]
        r1 = db["emotions"].delete_many({"pet_id": pet_id})
        r2 = db["missions"].delete_many({"pet_id": pet_id})
        r3 = db["health_logs"].delete_many({"pet_id": pet_id})
        r4 = db["usage_stats"].delete_many({"pet_id": pet_id})
        r5 = db["messages"].delete_many({"pet_id": pet_id})
        r6 = db["media_assets"].delete_many({"pet_id": pet_id})
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
            f"  RESET: 감정 {r1.deleted_count}·미션 {r2.deleted_count}·헬스 {r3.deleted_count}"
            f"·사용량 {r4.deleted_count}·메시지 {r5.deleted_count}·미디어 {r6.deleted_count} 삭제"
        )
        client.close()
    except Exception as e:
        print(f"  RESET 실패: {e.__class__.__name__}")


def _insert_health_mongo(pet_id: str, c: httpx.Client, headers: dict):
    """30일치 건강 데이터 MongoDB 직접 삽입 (날짜 지정용)."""
    try:
        client, col = _mongo_col("health_logs")
        today = date.today()
        for i in range(HEALTH_DAYS):
            d = (today - timedelta(days=i)).isoformat()
            # 회복 흐름: 최근일수록 건강 수치 좋음
            if i < 10:  # 최근 10일 — 완전 회복
                steps = random.randint(8000, 10000)
                sleep_h = round(random.uniform(7.0, 8.0), 1)
                late = random.randint(3, 12)
            elif i < 20:  # 10~20일 전 — 회복 중
                steps = random.randint(5000, 8000)
                sleep_h = round(random.uniform(6.0, 7.5), 1)
                late = random.randint(15, 35)
            else:  # 20~30일 전 — 초기 슬픔
                steps = random.randint(2000, 5000)
                sleep_h = round(random.uniform(4.5, 6.5), 1)
                late = random.randint(40, 80)
            col.update_one(
                {"pet_id": pet_id, "date": d},
                {
                    "$set": {
                        "steps": steps,
                        "sleep_hours": sleep_h,
                        "synced_at": datetime.now(timezone.utc),
                    }
                },
                upsert=True,
            )
            # usage_stats(야간 폰)는 날짜 지정 API 사용
            c.post(
                "/api/v1/usage-stats",
                json=[
                    {
                        "date": d,
                        "category": "SNS",
                        "minutes": random.randint(15, 50),
                        "late_night_minutes": late,
                    }
                ],
                headers=headers,
            )
            print(f"  헬스 {d}: {steps}보 / {sleep_h}h / 야간폰 {late}분")
            time.sleep(0.05)
        client.close()
    except Exception as e:
        print(f"  헬스 삽입 실패: {e.__class__.__name__} — {e}")


def _insert_missions_mongo(pet_id: str):
    try:
        client, col = _mongo_col("missions")
        today = datetime.now(timezone.utc).replace(
            hour=12, minute=0, second=0, microsecond=0
        )
        for i in range(MISSIONS_DAYS):
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
        print(f"  MongoDB: 과거 {MISSIONS_DAYS}일치 미션 삽입")
    except Exception as e:
        print(f"  미션 삽입 실패: {e.__class__.__name__}")


def _insert_message_mongo(pet_id: str):
    try:
        client, col = _mongo_col("messages")
        col.delete_many({"pet_id": pet_id})
        col.insert_one(
            {
                "pet_id": pet_id,
                "content": MESSAGE_1ST,
                "tone": "warm",
                "source": "local",
                "risk_level": 0,
                "first_person": True,
                "content_unlocked": True,
                "allow_first_person": True,
                "created_at": datetime.now(timezone.utc),
            }
        )
        client.close()
        print("  1인칭 편지 삽입 완료")
    except Exception as e:
        print(f"  편지 삽입 실패: {e.__class__.__name__}")


def _copy_media_from_demos(super_pet_id: str):
    """demo04 voiced_url·gif_url + demo03 slideshow_url 복사."""
    try:
        client, _ = _mongo_col("media_assets")
        db = client[MONGO_DB_NAME]
        assets = db["media_assets"]

        voiced_url = gif_url = video_url = slideshow_url = None

        # demo04 미디어 (voiced_url, gif_url)
        with httpx.Client(base_url=BASE, timeout=30) as hc:
            r = hc.post(
                "/api/v1/auth/login",
                json={"email": "demo04@demo.com", "password": "js1234"},
            )
            if r.status_code == 200:
                token = r.json()["access_token"]
                pets = hc.get(
                    "/api/v1/pets",
                    headers={"Authorization": f"Bearer {token}"},
                ).json()
                if pets:
                    demo04_pet_id = pets[0]["id"]
                    a = assets.find_one(
                        {"pet_id": demo04_pet_id, "status": "done"},
                        sort=[("created_at", -1)],
                    )
                    if a:
                        voiced_url = a.get("voiced_url")
                        gif_url = a.get("gif_url")
                        video_url = a.get("video_url")
                        print(f"  demo04 미디어: voiced={voiced_url} gif={gif_url}")
                    else:
                        print("  demo04 media_asset 없음")
            else:
                print("  demo04 로그인 실패 — 미디어 복사 스킵")

        # demo03 슬라이드쇼
        with httpx.Client(base_url=BASE, timeout=30) as hc:
            r = hc.post(
                "/api/v1/auth/login",
                json={"email": "demo03@demo.com", "password": "js1234"},
            )
            if r.status_code == 200:
                token = r.json()["access_token"]
                pets = hc.get(
                    "/api/v1/pets",
                    headers={"Authorization": f"Bearer {token}"},
                ).json()
                if pets:
                    demo03_pet_id = pets[0]["id"]
                    sa = assets.find_one(
                        {
                            "pet_id": demo03_pet_id,
                            "asset_type": "slideshow",
                            "status": "done",
                        }
                    )
                    if sa:
                        slideshow_url = sa.get("slideshow_url")
                        print(f"  demo03 슬라이드쇼: {slideshow_url}")
                    else:
                        print("  demo03 slideshow 없음")

        # super 계정에 삽입
        if voiced_url or gif_url:
            assets.insert_one(
                {
                    "pet_id": super_pet_id,
                    "status": "done",
                    "asset_type": "lp_voiced",
                    "voiced_url": voiced_url,
                    "gif_url": gif_url,
                    "video_url": video_url,
                    "created_at": datetime.now(timezone.utc),
                }
            )
            print("  LP voiced + GIF 복사 완료")
        else:
            print("  voiced_url/gif_url 없음 — 미디어 스킵")

        if slideshow_url:
            assets.insert_one(
                {
                    "pet_id": super_pet_id,
                    "status": "done",
                    "asset_type": "slideshow",
                    "slideshow_url": slideshow_url,
                    "created_at": datetime.now(timezone.utc),
                }
            )
            print("  슬라이드쇼 복사 완료")

        client.close()
    except Exception as e:
        print(f"  미디어 복사 실패: {e.__class__.__name__} — {e}")


def seed_checkins(c: httpx.Client, headers: dict, pet_id: str):
    for i, score in enumerate(CHECKINS):
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
        print(f"  체크인 {i + 1}: score={score} risk={risk}")
        time.sleep(0.5)


def seed_slideshow_trigger(c: httpx.Client, headers: dict, pet_id: str):
    """오늘 미션 1개 완료 → 슬라이드쇼 백그라운드 트리거."""
    r = c.get(f"/api/v1/missions/{pet_id}", headers=headers)
    missions = r.json() if r.status_code == 200 else []
    for m in missions:
        mid = m.get("id") or m.get("_id")
        if not mid or m.get("completed") or "slideshow" in str(mid):
            continue
        cr = c.patch(
            f"/api/v1/missions/{mid}/complete",
            json={"completed": True},
            headers=headers,
        )
        if cr.status_code == 200:
            print("  슬라이드쇼 트리거 미션 완료")
            return
    print("  슬라이드쇼 트리거 미션 없음 (이미 완료됐거나 없음)")


# ── 메인 ─────────────────────────────────────────────────────────────────────

print(f"\n── {EMAIL} ──")

with httpx.Client(base_url=BASE, timeout=90) as c:
    # 회원가입 (이미 있으면 409 무시)
    c.post(
        "/api/v1/auth/register",
        json={"email": EMAIL, "password": PASSWORD, "nickname": NICKNAME},
    )
    r = c.post("/api/v1/auth/login", json={"email": EMAIL, "password": PASSWORD})
    if r.status_code != 200:
        print(f"  로그인 실패: {r.status_code} {r.text}")
        raise SystemExit(1)
    token = r.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print("  로그인 성공")

    # 펫 조회 or 생성
    pets = c.get("/api/v1/pets", headers=headers).json()
    if pets:
        pet_id = pets[0]["id"]
        print(f"  기존 펫: {pet_id}")
    else:
        r = c.post("/api/v1/pets", json=PET, headers=headers)
        if r.status_code != 201:
            print(f"  펫 등록 실패: {r.status_code} {r.text}")
            raise SystemExit(1)
        pet_id = r.json()["id"]
        c.patch(f"/api/v1/pets/{pet_id}/memorial", headers=headers)
        print(f"  새 펫 등록: 하늘이 ({pet_id})")

    # 데이터 초기화
    if RESET:
        _reset_pet_data(pet_id)

    # 체크인 (20개, risk=0 확보)
    seed_checkins(c, headers, pet_id)

    # 헬스 (30일, MongoDB 직접)
    _insert_health_mongo(pet_id, c, headers)

    # 미션 (30일, MongoDB 직접)
    _insert_missions_mongo(pet_id)

    # 슬라이드쇼 트리거
    seed_slideshow_trigger(c, headers, pet_id)

    # 회복 게이트 확인
    r = c.get(f"/api/v1/emotions/recovery/{pet_id}", headers=headers)
    d = r.json()
    print(
        f"\n  gate={d.get('gate_status')} score={d.get('recovery_pct')} "
        f"content={d.get('content_unlocked')} allow_1st={d.get('allow_first_person')}"
    )

    # 1인칭 편지 삽입
    _insert_message_mongo(pet_id)

    # demo04 voiced_url + gif_url + demo03 slideshow 복사
    _copy_media_from_demos(pet_id)

print("\n완료 ✓")
print(f"계정: {EMAIL} / {PASSWORD}")
