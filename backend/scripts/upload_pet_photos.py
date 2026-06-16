"""시나리오 계정 사진 업로드 스크립트

seed_scenario.py 실행 후 사진을 따로 올릴 때 사용합니다.
PHOTO_DIR 폴더 안의 사진을 전 계정에 한 장씩 업로드합니다.
(첫 번째 파일을 대표 사진으로 사용)

실행: cd backend && py -3.13 scripts/upload_pet_photos.py
"""

from __future__ import annotations

import os
import httpx

BASE = "https://rainbow-bridge.duckdns.org"
PASSWORD = "js1234"

# ✏️ 사진 폴더 경로 — 폴더 안 첫 번째 사진이 대표 사진으로 업로드됩니다
PHOTO_DIR = "scripts/image"
FIRST_PHOTO = "scripts/image/KakaoTalk_20260616_094919370.jpg"  # 대표 사진 고정

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
    files = sorted(
        f for f in os.listdir(folder) if os.path.splitext(f)[1].lower() in exts
    )
    return [os.path.join(folder, f) for f in files]


photos = get_photos(PHOTO_DIR)
if not photos:
    print(f"사진 없음: {PHOTO_DIR}")
    exit(1)

print(
    f"사진 {len(photos)}장 발견. 첫 번째 사진을 대표 사진으로 업로드합니다: {photos[0]}"
)

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

        # 대표 사진 업로드 (고정)
        photo_path = FIRST_PHOTO
        with open(photo_path, "rb") as f:
            fname = os.path.basename(photo_path)
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
