"""시나리오 계정 사진 업로드 스크립트

seed_scenario.py 실행 후 사진을 따로 올릴 때 사용합니다.
PHOTO_DIR 폴더 안의 사진을 전부 모든 계정에 업로드합니다.
(사진이 많을수록 select_best_pet_photo가 더 좋은 사진을 고를 수 있음)

실행: cd backend && python3 scripts/upload_pet_photos.py
"""

from __future__ import annotations

import os

import httpx

BASE = "https://rainbow-bridge.duckdns.org"
PASSWORD = "js1234"

PHOTO_DIR = "scripts/image"

ACCOUNTS = [
    "demo00@demo.com",
    "demo01@demo.com",
    "demo02@demo.com",
    "demo03@demo.com",
    "demo04@demo.com",
    "demo05@demo.com",
]


def get_photos(folder: str) -> list[str]:
    exts = {".jpg", ".jpeg", ".png"}
    files = sorted(f for f in os.listdir(folder) if os.path.splitext(f)[1].lower() in exts)
    return [os.path.join(folder, f) for f in files]


photos = get_photos(PHOTO_DIR)
if not photos:
    print(f"사진 없음: {PHOTO_DIR}")
    exit(1)

print(f"사진 {len(photos)}장 발견. 계정마다 전부 업로드합니다.")

with httpx.Client(base_url=BASE, timeout=60) as c:
    for email in ACCOUNTS:
        print(f"\n── {email} ──")

        r = c.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
        if r.status_code != 200:
            print(f"  로그인 실패: {r.status_code}")
            continue
        headers = {"Authorization": f"Bearer {r.json()['access_token']}"}

        pets = c.get("/api/v1/pets", headers=headers).json()
        if not pets:
            print("  펫 없음")
            continue
        pet_id = pets[0]["id"]

        ok = 0
        for photo_path in photos:
            with open(photo_path, "rb") as f:
                fname = os.path.basename(photo_path)
                pr = c.post(
                    f"/api/v1/pets/{pet_id}/photo",
                    files={"file": (fname, f, "image/jpeg")},
                    headers=headers,
                )
            if pr.status_code == 200:
                ok += 1
            else:
                print(f"  실패({fname}): {pr.status_code} {pr.text[:60]}")
        print(f"  완료: {ok}/{len(photos)}장")

print("\n완료")
