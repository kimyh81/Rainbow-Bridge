"""슈퍼 계정 체크인 심기 (gate: open 상태로 만들기)"""

import httpx

BASE = "https://rainbow-bridge.duckdns.org"
ACCOUNTS = [
    "super@rainbow.dev",
    "super1@rainbow.dev",
    "super2@rainbow.dev",
    "super3@rainbow.dev",
    "super4@rainbow.dev",
    "super5@rainbow.dev",
]

with httpx.Client(base_url=BASE, timeout=30) as c:
    for email in ACCOUNTS:
        print(f"── {email} ──")
        r = c.post("/api/v1/auth/login", json={"email": email, "password": "super1234"})
        if r.status_code != 200:
            print(f"  로그인 실패: {r.status_code}")
            continue
        token = r.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        r = c.post(
            "/api/v1/pets",
            json={
                "name": "테스트펫",
                "species": "강아지",
                "period": "2020-01-01 ~ 2026-06-01",
                "caller_name": "보호자",
            },
            headers=headers,
        )
        if r.status_code == 201:
            pet_id = r.json()["id"]
        else:
            pets = c.get("/api/v1/pets", headers=headers).json()
            pet_id = pets[0]["id"] if pets else None
        if not pet_id:
            print("  펫 없음")
            continue
        print(f"  펫: {pet_id}")

        for i in range(5):
            r = c.post(
                "/api/v1/emotions",
                json={"pet_id": pet_id, "score": 9, "note": ""},
                headers=headers,
            )
            risk = r.json().get("risk_level", "?") if r.status_code == 201 else "err"
            print(f"  체크인 {i + 1}: risk={risk}")

        r = c.get(f"/api/v1/emotions/recovery/{pet_id}", headers=headers)
        d = r.json()
        print(f"  gate={d.get('gate_status')} score={d.get('recovery_pct')}")
        print()

print("완료")
