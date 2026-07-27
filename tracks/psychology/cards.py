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
# 파스텔 블루/보라 브랜드 무드 (2026-07-26 리브랜딩 — 그라디언트 로고와 통일).
# CORAL/TEAL 이름은 하위호환용 슬롯이고 실제 색은 페리윙클/스카이블루다.
BG = (248, 247, 253)          # 소프트 라벤더 화이트
INK = (58, 52, 92)            # 인디고 잉크
GREY = (150, 146, 162)
CORAL = (139, 122, 224)       # 주 accent — 페리윙클(보라)
CORAL_SOFT = (234, 230, 250)  # 소프트 라벤더
TEAL = (86, 150, 214)         # 보조 accent — 스카이블루
TEAL_SOFT = (224, 237, 251)   # 소프트 블루
RED_SOFT = (253, 226, 224)    # ✕ 말풍선(유지)
LINE = (231, 229, 243)

# 채널 로고 배지용 마스코트 컷아웃 (신규 파스텔 강아지, brand에서 생성)
MASCOT_CUT = ROOT / "data/assets/psychology/character/mascot_cut.png"
CHANNEL = "심리학가나디"

# 카카오톡 팔레트 (예문 채팅 UI — 실제 카톡 화면에 맞춤)
KAKAO_BG = (176, 197, 216)      # 채팅 배경 블루그레이
KAKAO_HEADER = (183, 203, 221)  # 상단 헤더 바 (배경보다 살짝 밝게)
KAKAO_YELLOW = (255, 227, 60)   # 내가 보낸 말풍선
KAKAO_WHITE = (255, 255, 255)   # 상대 말풍선
KAKAO_TEXT = (38, 38, 40)
KAKAO_TIME = (95, 108, 122)     # 시간 회색
KAKAO_UNREAD = (255, 214, 76)   # 안읽음 '1' (노랑)
KAKAO_ICON = (70, 78, 88)


def F(s):
    return ImageFont.truetype(FONT, s)


TITLE_LOGO = ROOT / "data/assets/psychology/character/title_logo.png"


def _brand_badge(im, d):
    """좌상단 채널 배지 — 디자인 로고 이미지(그라디언트) 그대로 사용.

    (마스코트+텍스트 락업 → 로고 이미지로 교체, 2026-07-26 사용자 요청.)
    로고가 없으면 마스코트+텍스트로 폴백.
    """
    x, y = 60, 34
    if TITLE_LOGO.exists():
        lg = Image.open(TITLE_LOGO).convert("RGBA")
        bh = 108
        r = bh / lg.height
        lg = lg.resize((max(1, round(lg.width * r)), bh), Image.LANCZOS)
        im.paste(lg, (x, y), lg)
        return
    tx = x
    if MASCOT_CUT.exists():
        m = Image.open(MASCOT_CUT).convert("RGBA")
        th = 84
        r = th / m.height
        m = m.resize((max(1, round(m.width * r)), th), Image.LANCZOS)
        im.paste(m, (x, y), m)
        tx = x + m.width + 18
    d.text((tx, y + 22), CHANNEL, font=F(40), fill=INK)


def _base(chip=None):
    """chip 인자는 하위 호환용으로 남기고 무시한다 — 상단은 항상 로고 배지."""
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    _brand_badge(im, d)
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


def _balance_wrap(d, text, font, max_w):
    """max_w 안에서 최소 줄 수로 감싸되, 줄 길이를 균형 있게 배분한다.
    그리디 줄바꿈은 마지막에 한 단어만 떨어지는 고아(예: '…닫는' / '것')를 만든다.
    → 같은 줄 수를 유지하는 최소 폭을 이분 탐색해, 마지막 줄이 홀로 짧아지지 않게 한다."""
    words = text.split()
    if len(words) <= 1:
        return words

    def greedy(width):
        lines, line = [], ""
        for w in words:
            trial = f"{line} {w}".strip()
            if d.textlength(trial, font=font) <= width or not line:
                line = trial
            else:
                lines.append(line); line = w
        if line:
            lines.append(line)
        return lines

    n = len(greedy(max_w))
    if n <= 1:
        return greedy(max_w)
    lo = int(max(d.textlength(w, font=font) for w in words)) + 1  # 최소한 한 단어는 들어가야
    hi = int(max_w)
    best = greedy(max_w)
    while lo <= hi:
        mid = (lo + hi) // 2
        cand = greedy(mid)
        if len(cand) <= n:
            best = cand; hi = mid - 1
        else:
            lo = mid + 1
    return best


def _draw_wrapped(d, text, font, fill, x, y, max_w, line_h):
    for line in _balance_wrap(d, text, font, max_w):
        d.text((x, y), line, font=font, fill=fill)
        y += line_h


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


def _x_mark(d, cx, cy, r, color, w=9):
    d.line((cx - r, cy - r, cx + r, cy + r), fill=color, width=w)
    d.line((cx + r, cy - r, cx - r, cy + r), fill=color, width=w)


def _check_mark(d, cx, cy, r, color, w=10):
    d.line((cx - r, cy, cx - r * 0.2, cy + r * 0.8), fill=color, width=w)
    d.line((cx - r * 0.2, cy + r * 0.8, cx + r, cy - r), fill=color, width=w)


def _heart(d, cx, cy, s, color):
    d.pieslice((cx - s, cy - s, cx, cy), 130, 360, fill=color)
    d.pieslice((cx, cy - s, cx + s, cy), 180, 50, fill=color)
    d.polygon([(cx - s * 0.92, cy - s * 0.1), (cx + s * 0.92, cy - s * 0.1),
               (cx, cy + s)], fill=color)


def _wrap(d, text, font, max_w):
    return _balance_wrap(d, text, font, max_w)


def _sent_bubble(d, text, font, right_x, top_y, max_text_w):
    """카톡 '내가 보낸' 노란 말풍선 (우측, 우상단 꼬리). bbox 반환."""
    lines = _wrap(d, text, font, max_text_w)
    lh = round(font.size * 1.34)
    pad_x, pad_y = 32, 22
    tw = max(d.textlength(ln, font=font) for ln in lines)
    bw, bh = tw + pad_x * 2, lh * len(lines) + pad_y * 2
    x0, y0 = right_x - bw, top_y
    d.rounded_rectangle((x0, y0, right_x, y0 + bh), radius=20, fill=KAKAO_YELLOW)
    d.polygon([(right_x - 6, y0 + 4), (right_x + 16, y0 - 4), (right_x - 2, y0 + 30)],
              fill=KAKAO_YELLOW)
    for i, ln in enumerate(lines):
        d.text((x0 + pad_x, y0 + pad_y + i * lh), ln, font=font, fill=KAKAO_TEXT)
    return (x0, y0, right_x, y0 + bh)


def _recv_bubble(im, d, text, font, left_x, top_y, max_text_w, avatar=None, name=None):
    """카톡 '상대' 흰 말풍선 (좌측, 아바타+이름). bbox 반환."""
    ax = left_x
    if avatar is not None and avatar.exists():
        av = Image.open(avatar).convert("RGBA").resize((84, 84), Image.LANCZOS)
        mask = Image.new("L", (84 * 4, 84 * 4), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, 84 * 4, 84 * 4), fill=255)
        im.paste(av, (ax, top_y), mask.resize((84, 84), Image.LANCZOS))
    bx0 = ax + 104
    ny = top_y
    if name:
        d.text((bx0 + 6, ny), name, font=F(28), fill=(70, 78, 92))
        ny += 42
    lines = _wrap(d, text, font, max_text_w)
    lh = round(font.size * 1.34)
    pad_x, pad_y = 30, 20
    tw = max(d.textlength(ln, font=font) for ln in lines)
    bw, bh = tw + pad_x * 2, lh * len(lines) + pad_y * 2
    d.rounded_rectangle((bx0, ny, bx0 + bw, ny + bh), radius=20, fill=KAKAO_WHITE)
    d.polygon([(bx0 + 6, ny + 4), (bx0 - 16, ny - 4), (bx0 + 2, ny + 30)], fill=KAKAO_WHITE)
    for i, ln in enumerate(lines):
        d.text((bx0 + pad_x, ny + pad_y + i * lh), ln, font=font, fill=KAKAO_TEXT)
    return (bx0, ny, bx0 + bw, ny + bh)


def quote_frame(text: str, good: bool, illust: Path, out: Path,
                chip: str = "말투 심리학") -> Path:
    """대사 한 줄이 주인공인 프레임 — 실제 카카오톡 화면 목업 + 일러스트.

    (2026-07-26: 레퍼런스처럼 헤더바·아바타·정확한 말풍선으로 리얼하게.
    '1'(안읽음)은 상대가 읽지 않은 bad 예문에서만 — 읽으면 사라진다.)
    """
    im, d = _base(chip)
    accent = TEAL if good else (224, 82, 65)

    # 상단 라벨 칩
    label = "이렇게 말해요" if good else "이렇게 말고"
    lw = d.textlength(label, font=F(40))
    cx0 = 90
    d.rounded_rectangle((cx0, 150, cx0 + 84 + lw + 44, 226), radius=38,
                        fill=(TEAL_SOFT if good else RED_SOFT))
    (_check_mark if good else _x_mark)(d, cx0 + 46, 189, 19, accent)
    d.text((cx0 + 88, 166), label, font=F(40), fill=accent)

    # 카톡 화면 패널
    px0, py0, px1, py1 = 90, 258, 1150, 862
    d.rounded_rectangle((px0, py0, px1, py1), radius=40, fill=KAKAO_BG)
    # 헤더 바
    hh = 96
    d.rounded_rectangle((px0, py0, px1, py0 + hh + 30), radius=40, fill=KAKAO_HEADER)
    d.rectangle((px0, py0 + 46, px1, py0 + hh), fill=KAKAO_HEADER)
    cy = py0 + hh // 2
    d.line([(px0 + 52, cy - 15), (px0 + 36, cy), (px0 + 52, cy + 15)], fill=KAKAO_ICON, width=6)
    d.text(((px0 + px1) // 2, cy), "상대방", font=F(38), fill=(45, 48, 55), anchor="mm")
    ix = px1 - 60
    for _ in range(3):  # 검색/통화/메뉴 자리 — 심플 아이콘 3
        pass
    # 검색(돋보기)
    d.ellipse((px1 - 260, cy - 16, px1 - 230, cy + 14), outline=KAKAO_ICON, width=5)
    d.line((px1 - 234, cy + 12, px1 - 224, cy + 22), fill=KAKAO_ICON, width=5)
    # 통화(수화기 단순화 — 둥근 사각)
    d.rounded_rectangle((px1 - 178, cy - 15, px1 - 150, cy + 15), radius=9, outline=KAKAO_ICON, width=5)
    # 메뉴(햄버거)
    for k in range(3):
        d.line((px1 - 96, cy - 14 + k * 14, px1 - 60, cy - 14 + k * 14), fill=KAKAO_ICON, width=5)
    d.line((px0, py0 + hh, px1, py0 + hh), fill=(160, 178, 196), width=2)

    # 내가 보낸 노란 말풍선
    bx = _sent_bubble(d, text, F(50), right_x=px1 - 46, top_y=py0 + hh + 74,
                      max_text_w=560)
    # 시간 + (bad일 때만) 안읽음 '1' — 말풍선 좌하단
    right_edge = bx[0] - 14
    tstr = "오후 9:14"
    d.text((right_edge, bx[3] - 34), tstr, font=F(26), fill=KAKAO_TIME, anchor="ra")
    if not good:  # 읽지 않음 → '1'. 읽으면 아무 표시 없음(카톡)
        d.text((right_edge, bx[3] - 74), "1", font=F(30), fill=KAKAO_UNREAD, anchor="ra")

    # 캐릭터 (우측)
    _illust(im, illust, (1210, 300, 1850, 820), pad_ratio=0.02)
    out.parent.mkdir(parents=True, exist_ok=True)
    im.save(out)
    return out
