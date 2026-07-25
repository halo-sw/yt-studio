"""심리 트랙 풀스크린 카드 엔진 — 이라스토야 일러스트 + 타이포 (1920x1080).

디자인: 웜 화이트 배경, 코럴 포인트, 큰 번호 배지, 우측 일러스트.
자막(흰 필 스타일)이 하단 ~y830에 얹히므로 본문은 그 위에서 끝낸다.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
FONT = str(ROOT / "data/assets/fonts/Pretendard-Bold.otf")
W, H = 1920, 1080
BG = (255, 253, 248)
INK = (31, 41, 55)
GREY = (140, 140, 135)
CORAL = (255, 122, 89)
CORAL_SOFT = (255, 235, 228)
TEAL = (42, 157, 143)
TEAL_SOFT = (223, 242, 239)
RED_SOFT = (253, 226, 224)
LINE = (232, 228, 220)


def F(s):
    return ImageFont.truetype(FONT, s)


def _base(chip="말투 심리학"):
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    cw = d.textlength(chip, font=F(28))
    d.rounded_rectangle((70, 54, 70 + cw + 40, 110), radius=28, fill=CORAL)
    d.text((90, 66), chip, font=F(28), fill=(255, 255, 255))
    return im, d


def _illust(im, src: Path, box, pad_ratio=0.06):
    """일러스트를 박스 안에 비율 유지로 배치 (흰 배경이라 그대로 얹음)."""
    x0, y0, x1, y1 = box
    tw, th = x1 - x0, y1 - y0
    ph = Image.open(src).convert("RGBA")
    r = min(tw / ph.width, th / ph.height) * (1 - pad_ratio)
    ph = ph.resize((round(ph.width * r), round(ph.height * r)), Image.LANCZOS)
    px = x0 + (tw - ph.width) // 2
    py = y0 + (th - ph.height) // 2
    im.paste(ph, (px, py), ph)


def item_card(num: int, title: str, tag: str, illust: Path, out: Path,
              sub: str = "") -> Path:
    im, d = _base()
    d.text((70, 210), f"{num:02d}", font=F(170), fill=CORAL)
    d.line((90, 420, 300, 420), fill=CORAL, width=8)
    d.text((70, 470), title, font=F(96), fill=INK)
    tw = d.textlength(tag, font=F(38))
    d.rounded_rectangle((70, 620, 70 + tw + 48, 692), radius=16, fill=TEAL_SOFT)
    d.text((94, 636), tag, font=F(38), fill=TEAL)
    if sub:
        d.text((70, 730), sub, font=F(36), fill=GREY)
    _illust(im, illust, (1050, 180, 1860, 800))
    out.parent.mkdir(parents=True, exist_ok=True)
    im.save(out)
    return out


def example_card(num: int, before: str, after: str, illust: Path, out: Path) -> Path:
    im, d = _base()
    d.text((70, 170), f"{num:02d} · 이렇게 바꿔보세요", font=F(48), fill=GREY)
    # BEFORE 말풍선
    d.rounded_rectangle((70, 270, 1150, 440), radius=28, fill=RED_SOFT)
    # ✕는 폰트 글리프가 없어 직접 그린다
    for dx in (0, 1):
        d.line((112 + dx, 320, 156 + dx, 386), fill=(214, 69, 65), width=10)
        d.line((156 + dx, 320, 112 + dx, 386), fill=(214, 69, 65), width=10)
    d.text((200, 310), before, font=F(52), fill=INK)
    # AFTER 말풍선
    d.rounded_rectangle((140, 500, 1250, 750), radius=28, fill=TEAL_SOFT)
    d.line((184, 594, 214, 630), fill=TEAL, width=12)
    d.line((214, 630, 268, 548), fill=TEAL, width=12)
    _draw_wrapped(d, after, F(52), INK, x=270, y=545, max_w=930, line_h=76)
    _illust(im, illust, (1290, 300, 1870, 780))
    out.parent.mkdir(parents=True, exist_ok=True)
    im.save(out)
    return out


def list_card(title: str, items: list[str], out: Path, illust: Path | None = None,
              chip: str = "말투 심리학") -> Path:
    im, d = _base(chip)
    d.text((70, 160), title, font=F(72), fill=INK)
    d.line((70, 270, W - 70, 270), fill=LINE, width=3)
    for i, t in enumerate(items):
        y = 310 + i * 85
        d.ellipse((80, y + 8, 124, y + 52), fill=CORAL_SOFT)
        d.text((102, y + 12), str(i + 1), font=F(30), fill=CORAL, anchor="ma")
        d.text((160, y), t, font=F(44), fill=INK)
    if illust:
        _illust(im, illust, (1420, 320, 1870, 780))
    out.parent.mkdir(parents=True, exist_ok=True)
    im.save(out)
    return out


def big_card(headline: str, sub: str, illust: Path, out: Path,
             accent: str | None = None, chip: str = "말투 심리학") -> Path:
    im, d = _base(chip)
    _draw_wrapped(d, headline, F(88), INK, x=70, y=250, max_w=1000, line_h=120)
    if accent:
        aw = d.textlength(accent, font=F(44))
        d.rounded_rectangle((70, 560, 70 + aw + 48, 640), radius=18, fill=CORAL_SOFT)
        d.text((94, 578), accent, font=F(44), fill=CORAL)
    if sub:
        d.text((70, 690), sub, font=F(38), fill=GREY)
    _illust(im, illust, (1100, 200, 1870, 800))
    out.parent.mkdir(parents=True, exist_ok=True)
    im.save(out)
    return out


def _draw_wrapped(d, text, font, fill, x, y, max_w, line_h):
    line = ""
    for word in text.split():
        trial = f"{line} {word}".strip()
        if d.textlength(trial, font=font) <= max_w or not line:
            line = trial
        else:
            d.text((x, y), line, font=font, fill=fill)
            y += line_h
            line = word
    if line:
        d.text((x, y), line, font=font, fill=fill)


# ---------------------------------------------------------------------------
# v2 — 일러스트 중심 프레임 (레퍼런스: 개념 나열형 지식 채널.
# 카드(문서) 문법이 아니라 일러스트가 화면의 주인공, 문장마다 그림 전환)
# ---------------------------------------------------------------------------

def focus_frame(illust: Path, out: Path, headline: str | None = None,
                num: str | None = None, chip: str = "말투 심리학") -> Path:
    """단색 배경 + 대형 중앙 일러스트 (+상단 헤드라인 한 줄)."""
    im, d = _base(chip)
    if num:
        d.text((960, 150), num, font=F(56), fill=CORAL, anchor="ma")
    if headline:
        d.text((960, 230), headline, font=F(84), fill=INK, anchor="ma")
        box = (360, 370, 1560, 790)
    else:
        box = (360, 220, 1560, 790)
    _illust(im, illust, box, pad_ratio=0.04)
    out.parent.mkdir(parents=True, exist_ok=True)
    im.save(out)
    return out


def quote_frame(text: str, good: bool, illust: Path, out: Path,
                chip: str = "말투 심리학") -> Path:
    """대사 한 줄이 주인공인 프레임 — 큰 말풍선 + 일러스트."""
    im, d = _base(chip)
    fill = TEAL_SOFT if good else RED_SOFT
    mark_c = TEAL if good else (214, 69, 65)
    # 말풍선은 위로 붙이고 높이를 줄여, 남는 세로 공간을 일러스트에 준다.
    # ✕✓ 대사가 이 채널의 핵심 문법이라 그림이 조연처럼 작아 보이면 안 된다.
    d.rounded_rectangle((160, 150, 1760, 430), radius=40, fill=fill)
    # 말풍선 꼬리
    d.polygon([(900, 430), (1000, 430), (930, 505)], fill=fill)
    if good:
        d.line((250, 275, 292, 327), fill=mark_c, width=16)
        d.line((292, 327, 366, 203), fill=mark_c, width=16)
    else:
        for dx in (0, 2):
            d.line((256 + dx, 227, 344 + dx, 347), fill=mark_c, width=16)
            d.line((344 + dx, 227, 256 + dx, 347), fill=mark_c, width=16)
    _draw_wrapped(d, text, F(64), INK, x=430, y=225, max_w=1250, line_h=92)
    # 하단 자막 필(~y830)을 침범하지 않는 최대 박스
    _illust(im, illust, (600, 500, 1320, 825), pad_ratio=0.02)
    out.parent.mkdir(parents=True, exist_ok=True)
    im.save(out)
    return out
