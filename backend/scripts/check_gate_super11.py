import httpx

BASE = "http://localhost:8000"
EMAIL = "super11@rainbow.dev"
PW = "123456"
PET_ID = "6a2d2dca06b558e441c3eb96"

with httpx.Client(base_url=BASE, timeout=60) as c:
    token = c.post("/api/v1/auth/login", json={"email": EMAIL, "password": PW}).json()[
        "access_token"
    ]
    h = {"Authorization": f"Bearer {token}"}

    r = c.get(f"/api/v1/emotions/recovery/{PET_ID}", headers=h)
    d = r.json()
    print(
        f"gate={d.get('gate_status')} score={d.get('recovery_score')} unlocked={d.get('content_unlocked')}"
    )
