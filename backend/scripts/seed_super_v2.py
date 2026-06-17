"""슈퍼 계정 0~5 생성 + gate open 세팅
- super0~5@rainbow.dev / super1234
- 펫 성별: 남아·여아·남아·여아·남아·여아 (교대)
- 체크인 10개씩 (score=9, risk=0) → gate=open 보장
"""

import httpx

BASE = "https://rainbow-bridge.duckdns.org"
PW = "super1234"

ACCOUNTS = [
    {
        "email": "super0@rainbow.dev",
        "nickname": "하늘이보호자",
        "pet_name": "하늘이",
        "gender": "남아",
    },
    {
        "email": "super1@rainbow.dev",
        "nickname": "별이보호자",
        "pet_name": "별이",
        "gender": "여아",
    },
    {
        "email": "super2@rainbow.dev",
        "nickname": "구름이보호자",
        "pet_name": "구름이",
        "gender": "남아",
    },
    {
        "email": "super3@rainbow.dev",
        "nickname": "봄이보호자",
        "pet_name": "봄이",
        "gender": "여아",
    },
    {
        "email": "super4@rainbow.dev",
        "nickname": "달이보호자",
        "pet_name": "달이",
        "gender": "남아",
    },
    {
        "email": "super5@rainbow.dev",
        "nickname": "콩이보호자",
        "pet_name": "콩이",
        "gender": "여아",
    },
]

with httpx.Client(base_url=BASE, timeout=60) as c:
    for acc in ACCOUNTS:
        print(f"\n── {acc['email']} ({acc['gender']}) ──")

        # 1. 회원가입 (이미 있으면 스킵)
        r = c.post(
            "/api/v1/auth/register",
            json={"email": acc["email"], "password": PW, "nickname": acc["nickname"]},
        )
        if r.status_code == 201:
            print("  ✅ 회원가입 완료")
        elif r.status_code == 409:
            print("  ℹ️  이미 존재 — 로그인 시도")
        else:
            print(f"  ❌ 회원가입 실패 ({r.status_code}): {r.text[:80]}")
            continue

        # 2. 로그인
        r = c.post("/api/v1/auth/login", json={"email": acc["email"], "password": PW})
        if r.status_code != 200:
            print(f"  ❌ 로그인 실패 ({r.status_code}): {r.text[:80]}")
            continue
        token = r.json()["access_token"]
        h = {"Authorization": f"Bearer {token}"}
        print("  ✅ 로그인 성공")

        # 3. 펫 등록 (이미 있으면 기존 펫 사용)
        r = c.post(
            "/api/v1/pets",
            json={
                "name": acc["pet_name"],
                "species": "강아지",
                "period": "2020-01-01 ~ 2026-06-01",
                "caller_name": "보호자",
                "gender": acc["gender"],
                "memories": [f"{acc['pet_name']}와 함께한 소중한 기억들"],
            },
            headers=h,
        )
        if r.status_code == 201:
            pet_id = r.json()["id"]
            print(f"  ✅ 펫 등록: {acc['pet_name']} ({pet_id})")
        else:
            pets = c.get("/api/v1/pets", headers=h).json()
            if not pets:
                print("  ❌ 펫 없음")
                continue
            pet_id = pets[0]["id"]
            print(f"  ℹ️  기존 펫 사용: {pet_id}")

        # 4. memorial_mode 설정
        c.patch(f"/api/v1/pets/{pet_id}", json={"memorial_mode": True}, headers=h)

        # 5. 체크인 10개 (gate open 보장)
        ok = 0
        for i in range(10):
            r = c.post(
                "/api/v1/emotions",
                json={"pet_id": pet_id, "score": 9, "note": "시연용 체크인"},
                headers=h,
            )
            if r.status_code == 201:
                ok += 1
        print(f"  ✅ 체크인 {ok}/10 완료")

        # 6. gate 확인
        r = c.get(f"/api/v1/emotions/recovery/{pet_id}", headers=h)
        d = r.json()
        print(
            f"  📊 gate={d.get('gate_status')} score={d.get('recovery_score')} unlocked={d.get('content_unlocked')}"
        )

print("\n\n완료!")
print("계정 요약:")
for acc in ACCOUNTS:
    print(f"  {acc['email']} / {PW}  ({acc['gender']}, 펫: {acc['pet_name']})")
