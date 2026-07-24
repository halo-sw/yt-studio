"""예린이의 부동산 뽀개기 — 채널 브랜드 상수·에셋 빌더.

크레딧이 든 생성물(로고·인트로 모션·프레젠터 체인·범퍼)은 data/assets/realestate/
에 영구 보관하고, 결정적(무비용) 에셋(마스크·링·로고 카드)은 여기서 재생성한다.

확정 이력 (2026-07-24 사용자 확정):
- 채널명 "예린이의 부동산 뽀개기", 보이스 Typecast Yena
- 프레젠터 = 거실 브이로거 예린 (스튜디오/자취방 버전 폐기)
- 분할 레이아웃(아영이네 구조): 메인 스크린 + 우측 캠/로고 카드
- 인트로 = Seedance 모션그래픽 + Yena 징글 (본편 훅 뒤에 삽입 — 0초 인트로 금지)
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
BRAND_DIR = ROOT / "data/assets/realestate/brand"
CHAR_DIR = ROOT / "data/assets/realestate/character"
FONT_PATH = ROOT / "data/assets/fonts/Pretendard-Bold.otf"

CHANNEL_NAME = "예린이의 부동산 뽀개기"
TAGLINE = "공고문은 어렵게, 정보는 쉽게"

# 영구 에셋 (재생성 시 크레딧 발생 — 교체는 사람이 결정)
LOGO_PNG = CHAR_DIR / "yerin_logo.png"            # GPT Image 2 스티커 로고
PRESENTER_BASE = CHAR_DIR / "yerin_living.png"     # NB2 거실 베이스 컷
PRESENTER_CHAIN = BRAND_DIR / "presenter_chain.mp4"  # 말하기 3클립 팔린드롬 체인(35s)
INTRO_MOTION = BRAND_DIR / "intro_motion.mp4"      # Seedance 로고 모션(5s, 무음)
BUMPER = BRAND_DIR / "bumper.mp4"                  # 인트로 최종본(모션+징글, 5.0s)
BUMPER_SEC = 5.0

# 분할 레이아웃 좌표 (1920x1080 캔버스)
CANVAS_COLOR = "0xF2EFE9"
MAIN_SIZE = (1496, 841)
MAIN_POS = (24, 120)
CAM_SIZE = (352, 198)
CAM_POS = (1544, 120)
CAM_RADIUS = 18
LOGO_CARD_POS = (1544, 360)


def _ensure(p: Path) -> Path:
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def build_cam_mask(out: Path | None = None) -> Path:
    """캠 라운드 마스크 (그레이스케일 — ffmpeg alphamerge용)."""
    out = _ensure(out or BRAND_DIR / "cam_mask.png")
    R = 4
    w, h = CAM_SIZE
    m = Image.new("L", (w * R, h * R), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, w * R, h * R), radius=CAM_RADIUS * R, fill=255)
    m.resize((w, h), Image.LANCZOS).save(out)
    return out


def build_cam_ring(out: Path | None = None) -> Path:
    out = _ensure(out or BRAND_DIR / "cam_ring.png")
    R = 4
    w, h = CAM_SIZE[0] + 10, CAM_SIZE[1] + 10
    ring = Image.new("RGBA", (w * R, h * R), (0, 0, 0, 0))
    ImageDraw.Draw(ring).rounded_rectangle(
        (2 * R, 2 * R, w * R - 2 * R, h * R - 2 * R),
        radius=(CAM_RADIUS + 3) * R, outline=(255, 255, 255, 240), width=5 * R)
    ring.resize((w, h), Image.LANCZOS).save(out)
    return out


def build_logo_card(out: Path | None = None) -> Path:
    """우측 사이드바 로고 카드 (흰 라운드 카드 + 로고 + 구독 안내)."""
    out = _ensure(out or BRAND_DIR / "logo_card.png")
    R = 4
    cw, ch = 352, 480
    card = Image.new("RGBA", (cw * R, ch * R), (0, 0, 0, 0))
    ImageDraw.Draw(card).rounded_rectangle((0, 0, cw * R, ch * R), radius=26 * R,
                                           fill=(255, 255, 255, 255))
    card = card.resize((cw, ch), Image.LANCZOS)
    logo = Image.open(LOGO_PNG).convert("RGBA").resize((312, 312), Image.LANCZOS)
    card.paste(logo, (20, 36), logo)
    d = ImageDraw.Draw(card)
    d.rounded_rectangle((36, 386, 316, 442), radius=22, fill=(25, 42, 65))
    d.text((176, 400), "구독하고 공고 알림 받기",
           font=ImageFont.truetype(str(FONT_PATH), 26), fill=(255, 255, 255), anchor="ma")
    card.save(out)
    return out


def ensure_brand_assets() -> dict[str, Path]:
    """결정적 에셋은 항상 재생성 가능. 크레딧 에셋은 존재 검증만 한다."""
    missing = [str(p) for p in (LOGO_PNG, PRESENTER_CHAIN, BUMPER) if not p.exists()]
    if missing:
        raise FileNotFoundError(
            "브랜드 크레딧 에셋 누락 — 재생성에는 Higgsfield 크레딧이 들어 사람 확인 필요: "
            + ", ".join(missing))
    return {
        "cam_mask": build_cam_mask(),
        "cam_ring": build_cam_ring(),
        "logo_card": build_logo_card(),
        "chain": PRESENTER_CHAIN,
        "bumper": BUMPER,
    }
