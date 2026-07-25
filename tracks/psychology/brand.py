"""심리 트랙 브랜드 자산 — 채널 「심리학가나디」 로고 카드 + 인트로 범퍼.

캐릭터는 **1회 생성 → 영구 재사용** 자산이다(realestate 프레젠터와 같은 방식).
편당 비주얼 비용 0원이라는 트랙 철학을 유지하기 위한 구조 —
바이블의 'Higgsfield 금지' 조항은 *편당* 생성 금지를 뜻하며,
브랜드 자산 1회 생성은 3인 합의로 허용된 예외다(2026-07-26).

⚠ 채널명과 동명의 이모티콘 캐릭터 IP(「듀.. 가나디」, HNF)가 실재한다.
  이 마스코트는 자체 생성물이며 해당 캐릭터의 그림·디자인을 참조하지 않는다.

범퍼 위치 규칙 (CLAUDE.md 11장 리텐션 규칙):
  0초 인트로 금지. **콜드오픈 훅이 끝난 뒤**에 넣는다.
  1편 기준 훅(씬 1~2) = 0:00~0:29.6 → 범퍼 삽입 지점 29.6s.

실행: .venv/bin/python -m tracks.psychology.brand
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
BRAND_DIR = ROOT / "data/assets/psychology/brand"
CHAR_DIR = ROOT / "data/assets/psychology/character"
FONT = str(ROOT / "data/assets/fonts/Pretendard-Bold.otf")

MASCOT = CHAR_DIR / "logo_c.png"          # 채택 컷 (굵은 마커 선 + 코럴 귀)
LOGO_CARD = BRAND_DIR / "logo_card.png"
JINGLE = BRAND_DIR / "bumper_voice.wav"
BUMPER = BRAND_DIR / "bumper.mp4"

CHANNEL = "심리학가나디"
TAGLINE = "이론 하나를, 내일 할 말 세 문장으로"
JINGLE_TEXT = "심리학가나디."
BUMPER_SEC = 4.0

W, H = 1920, 1080
INK = (31, 41, 55)
GREY = (140, 140, 135)
CORAL = (255, 122, 89)


def _F(s: int):
    return ImageFont.truetype(FONT, s)


def build_logo_card(out: Path | None = None) -> Path:
    """마스코트 + 채널명 + 태그라인 풀스크린 카드.

    배경색은 마스코트 이미지의 모서리 픽셀에서 뽑아 쓴다 — 생성물의 크림 배경과
    카드 배경이 정확히 일치해야 네모난 경계선이 안 보인다.
    """
    out = out or LOGO_CARD
    out.parent.mkdir(parents=True, exist_ok=True)
    mascot = Image.open(MASCOT).convert("RGB")
    bg = mascot.getpixel((4, 4))            # 크림 배경 샘플링 → 이음새 제거

    im = Image.new("RGB", (W, H), bg)
    d = ImageDraw.Draw(im)

    # 마스코트 — 상단 중앙, 화면 높이의 절반
    target_h = 540
    r = target_h / mascot.height
    m = mascot.resize((round(mascot.width * r), target_h), Image.LANCZOS)
    im.paste(m, ((W - m.width) // 2, 90))

    d.text((W // 2, 690), CHANNEL, font=_F(128), fill=INK, anchor="ma")
    d.line((W // 2 - 90, 860, W // 2 + 90, 860), fill=CORAL, width=8)
    d.text((W // 2, 900), TAGLINE, font=_F(40), fill=GREY, anchor="ma")
    im.save(out)
    return out


def build_jingle(out: Path | None = None) -> Path | None:
    """채널명 한 줄 징글. 무음 범퍼는 본편 중간에서 어색해 최소 음성을 넣는다."""
    out = out or JINGLE
    if out.exists():
        return out
    import os

    from core.schemas import Bible, Track, load_bible
    from core.tts import _synthesize_typecast

    key = os.getenv("TYPECAST_API_KEY")
    if not key:
        print("   TYPECAST_API_KEY 없음 — 징글 생략(무음 범퍼)")
        return None
    bible: Bible = load_bible(Track.PSYCHOLOGY)
    out.parent.mkdir(parents=True, exist_ok=True)
    path = _synthesize_typecast(JINGLE_TEXT, bible, out.with_suffix(".mp3"),
                                key, tone="호기심")
    return path


def build_bumper(out: Path | None = None) -> Path:
    """로고 카드 + 징글 → 4초 범퍼. 페이드 인/아웃 + 미세 줌(생동감).

    Ken Burns 금지 규칙은 '자막이 잘리는' 본편 카드에 적용되는 것이고,
    범퍼는 자막이 없으므로 아주 약한 줌(1.0→1.04)만 준다.
    """
    out = out or BUMPER
    card = build_logo_card()
    jingle = build_jingle()
    out.parent.mkdir(parents=True, exist_ok=True)

    fps = 30
    frames = int(BUMPER_SEC * fps)
    vf = (
        f"scale=3840:-1,zoompan=z='min(1.04,1+0.04*on/{frames})'"
        f":d={frames}:s={W}x{H}:fps={fps},"
        f"fade=t=in:st=0:d=0.4,fade=t=out:st={BUMPER_SEC - 0.4}:d=0.4,"
        f"format=yuv420p"
    )
    cmd = ["ffmpeg", "-v", "error", "-y", "-loop", "1", "-i", str(card)]
    if jingle:
        cmd += ["-i", str(jingle)]
    cmd += ["-t", str(BUMPER_SEC), "-vf", vf, "-r", str(fps)]
    if jingle:
        # 징글을 0.3s 뒤에 얹고 4초로 패딩 — 페이드인과 겹치지 않게
        # 징글에도 본편과 같은 -14 LUFS를 건다. 안 걸면 범퍼만 10 LU 넘게 작아져
        # 브랜드 사운드가 안 들린다(실측: loudnorm 없이 -27.3 vs 본편 -15.3).
        # loudnorm을 먼저 걸고 그 뒤에 지연·패딩 — 무음이 측정을 끌어내리지 않게.
        from core.assemble import NARRATION_LUFS

        cmd += ["-af", f"loudnorm=I={NARRATION_LUFS}:TP=-1.5:LRA=11,"
                       f"adelay=300|300,apad,atrim=0:{BUMPER_SEC},"
                       "aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo",
                "-c:a", "aac", "-b:a", "192k", "-shortest"]
    else:
        cmd += ["-an"]
    cmd += ["-c:v", "libx264", "-crf", "18", "-preset", "medium", str(out)]
    subprocess.run(cmd, check=True)
    return out


def insert_bumper(episode: Path, at: float, out: Path | None = None) -> Path:
    """에피소드의 `at`초 지점에 범퍼를 끼워 넣는다 (훅 직후).

    에피소드와 범퍼의 오디오 규격이 달라(44.1k 모노 vs 48k 스테레오) concat 전에
    맞춘다. 원본을 두 번 소비하므로 split/asplit 필수 —
    filter_complex에서 같은 라벨을 두 번 쓰면 일부 구간에 필터가 안 걸린다
    (CLAUDE.md 11장 ffmpeg 함정).
    """
    out = out or episode.with_name("episode_intro.mp4")
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries",
         "stream=sample_rate,channels", "-of", "csv=p=0", str(episode)],
        capture_output=True, text=True, check=True).stdout.strip().split(",")
    rate, ch = probe[0], "mono" if probe[1] == "1" else "stereo"

    fc = (
        f"[0:v]split=2[vs0][vs2];[0:a]asplit=2[as0][as2];"
        f"[vs0]trim=0:{at},setpts=PTS-STARTPTS[v0];"
        f"[as0]atrim=0:{at},asetpts=PTS-STARTPTS[a0];"
        f"[vs2]trim=start={at},setpts=PTS-STARTPTS[v2];"
        f"[as2]atrim=start={at},asetpts=PTS-STARTPTS[a2];"
        f"[1:v]setpts=PTS-STARTPTS[v1];"
        f"[1:a]aformat=sample_rates={rate}:channel_layouts={ch},"
        f"asetpts=PTS-STARTPTS[a1];"
        f"[v0][a0][v1][a1][v2][a2]concat=n=3:v=1:a=1[v][a]"
    )
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-i", str(episode), "-i", str(BUMPER),
         "-filter_complex", fc, "-map", "[v]", "-map", "[a]",
         "-c:v", "libx264", "-crf", "18", "-preset", "medium",
         "-c:a", "aac", "-b:a", "192k", str(out)], check=True)
    return out


def main() -> None:
    print("1) 로고 카드")
    print(f"   → {build_logo_card()}")
    print("2) 범퍼 (4초, 훅 뒤 삽입용)")
    print(f"   → {build_bumper()}")


if __name__ == "__main__":
    main()
