"""
온보딩 화면 목업 PNG 생성 스크립트
실행: python make_onboard_png.py
출력: onboard_mockup.png (현재 폴더)
"""

from PIL import Image, ImageDraw, ImageFont

# ── 캔버스 (iPhone 14 Pro 기준) ─────────────────────────────────
W, H = 393, 852
BG_PATH = "frontend-rn/assets/onboard_bg.png"

# ── 색상 ────────────────────────────────────────────────────────
INK    = (255, 255, 255, 255)   # 흰 텍스트
SHADOW = (60,  30,  80,  160)   # 텍스트 가독성용 그림자
BTN_BG = (138, 92,  176, 200)   # 시작하기 버튼


# ── 폰트 ────────────────────────────────────────────────────────
def load_font(path, size):
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()


MALGUN_B = "C:/Windows/Fonts/malgunbd.ttf"
MALGUN   = "C:/Windows/Fonts/malgun.ttf"

f_h1  = load_font(MALGUN_B, 30)
f_btn = load_font(MALGUN_B, 17)


def text_size(draw, text, font):
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def draw_text_with_shadow(draw, pos, text, font, fill, shadow_fill, offset=3):
    draw.text((pos[0] + offset, pos[1] + offset), text, font=font, fill=shadow_fill)
    draw.text(pos, text, font=font, fill=fill)


# ── 1. 배경 이미지 (원본 비율 유지 + 커버 크롭) ─────────────────
bg_src = Image.open(BG_PATH).convert("RGBA")
src_w, src_h = bg_src.size
scale = max(W / src_w, H / src_h)
nw, nh = int(src_w * scale), int(src_h * scale)
bg_src = bg_src.resize((nw, nh), Image.LANCZOS)
ox = (nw - W) // 2
oy = (nh - H) // 2
canvas = bg_src.crop((ox, oy, ox + W, oy + H))

# ── 2. 텍스트 세로 중앙 약간 위쪽 배치 ──────────────────────────
draw = ImageDraw.Draw(canvas)

line1 = "아이가 강아지별로"
line2 = "이사를 준비하고 있어요"

w1, h1 = text_size(draw, line1, f_h1)
w2, h2 = text_size(draw, line2, f_h1)

gap = 14
block_h = h1 + gap + h2
y_start = H - 220   # 하단 배치

x1 = (W - w1) // 2
x2 = (W - w2) // 2

draw_text_with_shadow(draw, (x1, y_start),          line1, f_h1, INK, SHADOW)
draw_text_with_shadow(draw, (x2, y_start + h1 + gap), line2, f_h1, INK, SHADOW)

# ── 3. 시작하기 버튼 ─────────────────────────────────────────────
BTN_W, BTN_H = 240, 52
btn_x = (W - BTN_W) // 2
btn_y = y_start + block_h + 60

btn_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
ImageDraw.Draw(btn_layer).rounded_rectangle(
    [btn_x, btn_y, btn_x + BTN_W, btn_y + BTN_H],
    radius=26, fill=BTN_BG
)
canvas = Image.alpha_composite(canvas, btn_layer)

draw = ImageDraw.Draw(canvas)
bw, bh = text_size(draw, "시작하기", f_btn)
draw.text(
    (btn_x + (BTN_W - bw) // 2, btn_y + (BTN_H - bh) // 2),
    "시작하기", font=f_btn, fill=(255, 255, 255, 255)
)

# ── 4. 저장 ───────────────────────────────────────────────────────
out_path = "onboard_mockup.png"
canvas.convert("RGB").save(out_path, "PNG")
print(f"저장 완료: {out_path}  ({W}×{H}px)")
