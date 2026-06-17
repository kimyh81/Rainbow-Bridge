"""super11@rainbow.dev 시연 계정 생성 + gate open 세팅"""

import httpx

BASE = "http://localhost:8000"
EMAIL = "super11@rainbow.dev"
PW = "123456"

with httpx.Client(base_url=BASE, timeout=30) as c:
    # 1. 회원가입
    r = c.post(
        "/api/v1/auth/register",
        json={
            "email": EMAIL,
            "password": PW,
            "name": "시연계정11",
            "nickname": "초롱이보호자",
        },
    )
    print("register:", r.status_code, r.text[:150])
    if r.status_code not in (200, 201):
        print("이미 가입된 계정이거나 오류. 로그인만 시도합니다.")

    # 2. 로그인
    r = c.post("/api/v1/auth/login", json={"email": EMAIL, "password": PW})
    if r.status_code != 200:
        print("로그인 실패:", r.text)
        exit(1)
    token = r.json()["access_token"]
    h = {"Authorization": f"Bearer {token}"}
    print("로그인 성공")

    # 3. 펫 생성 (이미 있으면 기존 펫 사용)
    r = c.post(
        "/api/v1/pets",
        json={
            "name": "초롱이",
            "species": "강아지",
            "period": "2020-01-01 ~ 2026-06-01",
            "caller_name": "보호자",
            "gender": "남아",
        },
        headers=h,
    )
    if r.status_code == 201:
        pet_id = r.json().get("id") or r.json().get("_id")
        print("펫 생성:", pet_id)
    else:
        pets = c.get("/api/v1/pets", headers=h).json()
        pet_id = pets[0]["id"] if pets else None
        print("기존 펫 사용:", pet_id)

    if not pet_id:
        print("펫 없음. 종료.")
        exit(1)

    # 4. 체크인 14개 심기 (gate=open 보장)
    for i in range(14):
        r = c.post(
            "/api/v1/emotions",
            json={"pet_id": pet_id, "score": 9, "note": ""},
            headers=h,
        )
        print(f"  체크인{i+1}: {r.status_code}")

    # 5. gate 확인
    r = c.get(f"/api/v1/emotions/recovery/{pet_id}", headers=h)
    d = r.json()
    print(
        f"\n결과: gate={d.get('gate_status')} score={d.get('recovery_score')} unlocked={d.get('content_unlocked')}"
    )
    print("완료!")
