"""시나리오 계정 사진 업로드 스크립트

seed_scenario.py 실행 후 사진을 따로 올릴 때 사용합니다.
PHOTO_PATH 만 바꾸고 실행하면 js00~js05 전 계정에 동일한 사진이 업로드됩니다.

실행: cd backend && py -3.13 scripts/upload_pet_photos.py
"""

from __future__ import annotations

import httpx

BASE = "https://rainbow-bridge.duckdns.org"
PASSWORD = "js1234"

# ✏️ 여기에 사진 파일 경로 입력
PHOTO_PATH = "C:/Users/user/Desktop/haneuli.jpg"

ACCOUNTS = [
    "demo00@demo.com",
    "demo01@demo.com",
    "demo02@demo.com",
    "demo03@demo.com",
    "demo04@demo.com",
    "demo05@demo.com",
]


with httpx.Client(base_url=BASE, timeout=60) as c:
    for email in ACCOUNTS:
        print(f"\n── {email} ──")

        # 로그인
        r = c.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
        if r.status_code != 200:
            print(f"  로그인 실패: {r.status_code}")
            continue
        headers = {"Authorization": f"Bearer {r.json()['access_token']}"}

        # 펫 조회
        pets = c.get("/api/v1/pets", headers=headers).json()
        if not pets:
            print(f"  펫 없음 — seed_scenario.py 먼저 실행하세요")
            continue
        pet_id = pets[0]["id"]

        # 사진 업로드
        with open(PHOTO_PATH, "rb") as f:
            fname = PHOTO_PATH.replace("\\", "/").split("/")[-1]
            pr = c.post(
                f"/api/v1/pets/{pet_id}/photo",
                files={"file": (fname, f, "image/jpeg")},
                headers=headers,
            )
        if pr.status_code == 200:
            print(f"  완료: {pr.json().get('photo_url', '')[:70]}")
        else:
            print(f"  실패: {pr.status_code} {pr.text[:80]}")

print("\n완료")
