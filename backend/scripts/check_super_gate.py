import httpx

BASE = "https://rainbow-bridge.duckdns.org"
ACCOUNTS = [
    "super@rainbow.dev",
    "super1@rainbow.dev",
    "super2@rainbow.dev",
    "super3@rainbow.dev",
    "super5@rainbow.dev",
]

with httpx.Client(base_url=BASE, timeout=30) as c:
    for email in ACCOUNTS:
        token = c.post(
            "/api/v1/auth/login", json={"email": email, "password": "super1234"}
        ).json()["access_token"]
        pets = c.get(
            "/api/v1/pets", headers={"Authorization": f"Bearer {token}"}
        ).json()
        if not pets:
            print(f"{email}: 펫 없음")
            continue
        pet_id = pets[0]["id"]
        r = c.get(
            f"/api/v1/emotions/recovery/{pet_id}",
            headers={"Authorization": f"Bearer {token}"},
        ).json()
        print(
            f"{email}: gate={r.get('gate_status')} score={r.get('recovery_pct')} unlocked={r.get('content_unlocked')}"
        )
