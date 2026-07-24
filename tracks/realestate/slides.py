"""공고 뽀개기 슬라이드 엔진 v3 — 스펙(dict) 기반 인포그래픽 렌더러.

디자인 시스템 (2026-07-24 확정): 밝은 종이 배경 + 옐로 브랜드 칩 + 큰 네이비
타이포 + 얇은 디바이더 + 핵심 값 옐로 마커 + 우측 라운드 사진 패널.
자막 밴드(y≈830~) 아래로 본문 내용이 내려가지 않게 각 렌더러가 y를 관리한다.

슬라이드 스펙 형식 (에피소드 yaml의 scenes.slides[sid]):
  {type: kv|compare|numbered|checklist|calendar|timeline|split|hero,
   title: str, photo: <씬번호|경로|None>, ...타입별 필드}
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
FONT_PATH = str(ROOT / "data/assets/fonts/Pretendard-Bold.otf")

W, H = 1920, 1080
BG = (251, 250, 247)
NAVY = (25, 42, 65)
INK = (40, 46, 56)
GREY = (150, 148, 142)
LINE = (229, 225, 218)
YEL = (255, 214, 76)
YEL_SOFT = (255, 243, 205)
RED = (224, 82, 65)
WHITE = (255, 255, 255)

PHOTO_BOX = (1210, 300, 1850, 700)  # 우측 사진 패널 기본 위치 (캠/자막과 안 겹침)


def F(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(FONT_PATH, size)


def _base(title: str, kicker: str = "공고 뽀개기"):
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    kw = d.textlength(kicker, font=F(30))
    d.rounded_rectangle((70, 56, 70 + kw + 44, 116), radius=30, fill=YEL)
    d.text((92, 68), kicker, font=F(30), fill=NAVY)
    d.text((70, 146), title, font=F(58), fill=NAVY)
    d.line((70, 240, W - 70, 240), fill=LINE, width=2)
    return im, d


def _footer(d, text):
    if text:
        d.text((70, H - 56), text, font=F(24), fill=GREY)


def _photo_panel(im, src: Path, box=PHOTO_BOX):
    x0, y0, x1, y1 = box
    ph = Image.open(src).convert("RGB")
    tw, th = x1 - x0, y1 - y0
    r = max(tw / ph.width, th / ph.height)
    ph = ph.resize((round(ph.width * r), round(ph.height * r)), Image.LANCZOS)
    cx, cy = (ph.width - tw) // 2, (ph.height - th) // 2
    ph = ph.crop((cx, cy, cx + tw, cy + th))
    mask = Image.new("L", (tw * 4, th * 4), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, tw * 4, th * 4), radius=88, fill=255)
    im.paste(ph, (x0, y0), mask.resize((tw, th), Image.LANCZOS))
    ImageDraw.Draw(im).rounded_rectangle((x0, y0, x1, y1), radius=22, outline=LINE, width=3)


def _kv(d, x, y, label, value, vsize=62, hl=False):
    d.text((x, y), label, font=F(30), fill=GREY)
    if hl:
        w = d.textlength(value, font=F(vsize))
        d.rounded_rectangle((x - 14, y + 44, x + w + 22, y + 44 + vsize + 26),
                            radius=14, fill=YEL_SOFT)
    d.text((x, y + 54), value, font=F(vsize), fill=NAVY)


# ---------------------------------------------------------------------------
# 타입별 렌더러 — spec 필드는 docstring 참조
# ---------------------------------------------------------------------------

def _render_kv(im, d, spec):
    """items: [{label, value, hl?, size?}] (최대 3~4개), 사진 있으면 x1 제한."""
    items = spec["items"]
    y0 = spec.get("y0", 290)
    gap = spec.get("gap", (760 - y0) // max(len(items) - 1, 1) + 60) if len(items) > 1 else 0
    gap = min(gap, 220)
    for i, it in enumerate(items):
        _kv(d, 70, y0 + i * gap, it["label"], it["value"],
            vsize=it.get("size", 66 if spec.get("photo") else 76), hl=it.get("hl", False))


def _render_compare(im, d, spec):
    """sections: [{tag, color?, headline, sub}] 2개."""
    ys = ((290, 560), (610, None))
    for (sec, (y, div)) in zip(spec["sections"], ys):
        color = RED if sec.get("color") == "red" else NAVY
        d.text((70, y), sec["tag"], font=F(46), fill=color)
        d.text((70, y + 80), sec["headline"], font=F(56), fill=INK)
        d.text((70, y + 162), sec.get("sub", ""), font=F(38), fill=GREY)
        if div:
            d.line((70, div, W - 70, div), fill=LINE, width=2)


def _render_numbered(im, d, spec):
    """items: [str] — 옐로 번호 원 + 텍스트."""
    for i, t in enumerate(spec["items"]):
        y = 310 + i * 180
        d.ellipse((70, y, 150, y + 80), fill=YEL)
        d.text((110, y + 14), str(i + 1), font=F(44), fill=NAVY, anchor="ma")
        d.text((190, y + 12), t, font=F(50), fill=INK)
        if i < len(spec["items"]) - 1:
            d.line((190, y + 140, W - 70, y + 140), fill=LINE, width=2)


def _render_checklist(im, d, spec):
    for i, t in enumerate(spec["items"]):
        y = 300 + i * 140
        d.rounded_rectangle((70, y, 130, y + 60), radius=12, outline=NAVY, width=5)
        d.text((170, y + 2), t, font=F(48), fill=INK)


def _render_calendar(im, d, spec):
    """left: {month, big, sub}(옐로 강조) / right: {month, lines[]} / todo: str."""
    L, Rt = spec["left"], spec["right"]
    d.rounded_rectangle((70, 300, 930, 620), radius=22, fill=YEL_SOFT)
    d.text((110, 340), L["month"], font=F(40), fill=GREY)
    d.text((110, 400), L["big"], font=F(84), fill=NAVY)
    d.text((110, 530), L["sub"], font=F(44), fill=RED)
    d.rounded_rectangle((990, 300, 1850, 620), radius=22, fill=WHITE, outline=LINE, width=3)
    d.text((1030, 340), Rt["month"], font=F(40), fill=GREY)
    for i, ln in enumerate(Rt["lines"]):
        d.text((1030, 410 + i * 90), ln, font=F(56), fill=NAVY)
    if spec.get("todo"):
        d.text((70, 720), spec["todo"], font=F(42), fill=INK)


def _render_timeline(im, d, spec):
    """steps: [{t, s}] 4개, hl_n: 앞에서 몇 개를 붉게, note."""
    x = 70
    hl_n = spec.get("hl_n", 2)
    for i, st in enumerate(spec["steps"]):
        d.rounded_rectangle((x, 360, x + 400, 620), radius=22, fill=WHITE, outline=LINE, width=3)
        d.text((x + 36, 400), st["t"], font=F(46), fill=RED if i < hl_n else GREY)
        d.text((x + 36, 500), st["s"], font=F(44), fill=NAVY)
        if i < len(spec["steps"]) - 1:
            d.text((x + 415, 460), "→", font=F(56), fill=GREY)
        x += 470
    if spec.get("note"):
        d.text((70, 720), spec["note"], font=F(42), fill=INK)


def _render_split(im, d, spec):
    """두 박스 대비 (예: 내 몫 vs LH 몫). boxes: [{label, value, color?}], head, note."""
    if spec.get("head"):
        d.text((70, 300), spec["head"], font=F(44), fill=INK)
    coords = ((70, 420, 900, 680), (1010, 420, 1850, 680))
    for box, c in zip(spec["boxes"], coords):
        color = RED if box.get("color") == "red" else NAVY
        outline = (240, 200, 195) if box.get("color") == "red" else LINE
        d.rounded_rectangle(c, radius=22, fill=WHITE, outline=outline, width=3)
        d.text((c[0] + 40, c[1] + 40), box["label"], font=F(36), fill=GREY)
        d.text((c[0] + 40, c[1] + 120), box["value"], font=F(64), fill=color)
    if spec.get("note"):
        d.text((70, 760), spec["note"], font=F(36), fill=RED)


def _render_hero(im, d, spec):
    """대형 숫자 1개: label, big, sub, note."""
    d.text((70, 320), spec.get("label", ""), font=F(44), fill=GREY)
    d.text((70, 400), spec["big"], font=F(120), fill=NAVY)
    if spec.get("sub"):
        d.text((70, 600), spec["sub"], font=F(42), fill=INK)
    if spec.get("note"):
        d.text((70, 680), spec["note"], font=F(34), fill=RED)


_RENDERERS = {
    "kv": _render_kv, "compare": _render_compare, "numbered": _render_numbered,
    "checklist": _render_checklist, "calendar": _render_calendar,
    "timeline": _render_timeline, "split": _render_split, "hero": _render_hero,
}


def render_slide(spec: dict, out_png: Path, vis_dir: Path,
                 footer: str = "출처: 공고·언론 보도 종합 — 세부 기준은 공고문 원문 확인") -> Path:
    im, d = _base(spec["title"], spec.get("kicker", "공고 뽀개기"))
    _RENDERERS[spec["type"]](im, d, spec)
    photo = spec.get("photo")
    if photo is not None:
        src = vis_dir / f"{int(photo):02d}.png" if isinstance(photo, int) else Path(photo)
        if src.exists():
            _photo_panel(im, src, tuple(spec.get("photo_box", PHOTO_BOX)))
    _footer(d, spec.get("footer", footer))
    out_png.parent.mkdir(parents=True, exist_ok=True)
    im.save(out_png)
    return out_png
