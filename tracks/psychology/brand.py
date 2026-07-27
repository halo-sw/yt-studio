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
# 동적 인트로 소스 (2026-07-26 사용자 요청): 강아지가 공부해 뇌·심리를 파헤치는
# Seedance 2.0 애니메이션(5s). GPT Image 2로 만든 dog_study(마스코트 참조) 장면을
# start-image로 i2v. 크레딧 자산이라 1회 생성 → 영구 재사용(realestate 방식).
INTRO_MOTION = BRAND_DIR / "intro_motion.mp4"
ENDCARD = BRAND_DIR / "endcard.png"       # 채널명 하단 락업 오버레이
BGM_BED = ROOT / "data/assets/psychology/bgm/bed_calm.mp3"  # 본편과 동일 BGM(연속성)

CHANNEL = "심리학가나디"
TAGLINE = "이론 하나를, 내일 할 말 세 문장으로"
JINGLE_TEXT = "심리학가나디."
BUMPER_SEC = 5.0

W, H = 1920, 1080
INK = (31, 41, 55)
GREY = (140, 140, 135)
CORAL = (255, 122, 89)
RED_SOFT = (253, 226, 224)   # ✕ 말풍선 (cards.py와 동일 팔레트)


def _F(s: int):
    return ImageFont.truetype(FONT, s)


def _black(s: int):
    return ImageFont.truetype(str(ROOT / "data/assets/fonts/Pretendard-Black.otf"), s)


def mascot_cutout(out: Path | None = None) -> Path:
    """마스코트의 크림 배경을 투명하게 뚫은 컷아웃.

    본편 카드(`cards._illust`)는 알파로 합성하므로 배경이 박힌 RGB를 그대로 넣으면
    네모난 크림 사각형이 얹힌다. 강아지 몸통도 흰색이라 색상 키잉은 몸까지 뚫는다
    → **네 모서리에서 flood fill**로 '바깥과 연결된' 배경만 제거한다.
    """
    out = out or CHAR_DIR / "logo_c_cut.png"
    if out.exists():
        return out
    im = Image.open(MASCOT).convert("RGB")
    w, h = im.size
    px = im.load()
    bg = px[2, 2]
    tol = 26

    def near(c):
        return all(abs(c[i] - bg[i]) <= tol for i in range(3))

    # BFS로 모서리에서 연결된 배경만 수집
    seen = bytearray(w * h)
    stack = [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)]
    while stack:
        x, y = stack.pop()
        if not (0 <= x < w and 0 <= y < h):   # 인덱스 계산 전에 경계부터 본다
            continue
        i = y * w + x
        if seen[i] or not near(px[x, y]):
            continue
        seen[i] = 1
        stack += [(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)]

    rgba = im.convert("RGBA")
    ap = rgba.load()
    for y in range(h):
        row = y * w
        for x in range(w):
            if seen[row + x]:
                r, g, b, _ = ap[x, y]
                ap[x, y] = (r, g, b, 0)
    # 여백 잘라내기 — 카드에서 최대 크기로 앉히기 위해
    rgba = rgba.crop(rgba.getbbox())
    out.parent.mkdir(parents=True, exist_ok=True)
    rgba.save(out)
    return out


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


TITLE_LOGO = CHAR_DIR / "title_logo.png"   # 디자인 타이틀 로고(GPT Image 2, 배경 투명)


def build_endcard(out: Path | None = None) -> Path:
    """채널 타이틀 로고 오버레이(투명 PNG) — 동적 범퍼 끝에 페이드인.

    (2026-07-26 사용자 요청: 밋밋한 텍스트 대신 디자인 스티커 로고를 삽입.)
    로고가 없으면 텍스트 락업으로 폴백.
    """
    out = out or ENDCARD
    out.parent.mkdir(parents=True, exist_ok=True)
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    if TITLE_LOGO.exists():
        logo = Image.open(TITLE_LOGO).convert("RGBA")
        # 강아지가 얹힌 세로가 긴 로고 — 프레임 안에 태그라인까지 들어오게 축소·중앙
        tw = 980
        r = tw / logo.width
        logo = logo.resize((tw, round(logo.height * r)), Image.LANCZOS)
        lx, ly = (W - logo.width) // 2, 250
        im.paste(logo, (lx, ly), logo)
        tag_y = ly + logo.height + 30
        tf = _F(40)
        tw2 = d.textlength(TAGLINE, font=tf)
        d.rounded_rectangle((W // 2 - tw2 // 2 - 32, tag_y - 8,
                             W // 2 + tw2 // 2 + 32, tag_y + 62), radius=34,
                            fill=(255, 255, 255, 225))
        d.text((W // 2, tag_y), TAGLINE, font=tf, fill=(110, 100, 140), anchor="ma")
    else:
        d.rounded_rectangle((W // 2 - 560, 815, W // 2 + 560, 1000), radius=40,
                            fill=(255, 251, 242, 235))
        d.text((W // 2, 838), CHANNEL, font=_black(96), fill=INK, anchor="ma")
        d.line((W // 2 - 90, 958, W // 2 + 90, 958), fill=CORAL, width=8)
        d.text((W // 2, 976), TAGLINE, font=_F(36), fill=GREY, anchor="ma")
    im.save(out)
    return out


def build_bumper(out: Path | None = None, include_bgm: bool = False,
                 overlay_logo: bool = False) -> Path:
    """동적 인트로 범퍼. intro_motion이 곧 '심리학가나디 로고 애니메이션'이므로
    (2026-07-26 확정) 그 자체를 재생하고 징글만 얹는다. overlay_logo=True일 때만
    별도 엔드카드 로고를 위에 덧그린다(구 강아지-공부 인트로 호환용).

    소스가 없으면 예외 — 정적 폴백은 쓰지 않는다(동적 로고 인트로가 확정 자산).
    """
    out = out or BUMPER
    if not INTRO_MOTION.exists():
        raise FileNotFoundError(
            f"동적 인트로 소스 없음: {INTRO_MOTION} — Seedance 재생성 필요(크레딧).")
    from core.assemble import NARRATION_LUFS
    jingle = build_jingle()
    bgm = BGM_BED if (include_bgm and BGM_BED.exists()) else None
    out.parent.mkdir(parents=True, exist_ok=True)

    enter = 1.6   # 징글이 로고와 함께 들어오는 시점
    ms = int(enter * 1000)
    # 로고 애니메이션 자체를 재생 (엔드카드 오버레이 없음 = 로고 중복 방지).
    # 끝을 검게 페이드아웃하지 않는다(로고가 까만 배경에 뜨는 사고 방지).
    # 페이드인 없음 — insert_bumper의 크로스페이드가 전환을 담당(검은 딥 방지)
    dog = ("[1:v]scale=1920:1080:force_original_aspect_ratio=increase,"
           "crop=1920:1080,setsar=1,fps=30[v]")
    if overlay_logo:
        endcard = build_endcard()
        dog = (
            "[1:v]scale=1920:1080:force_original_aspect_ratio=increase,"
            "crop=1920:1080,setsar=1,fps=30,fade=t=in:st=0:d=0.35[dog];"
            f"[0:v]format=rgba,fade=t=in:st=2.2:d=0.45:alpha=1[ec];"
            "[dog][ec]overlay=0:'60*max(0,1-(t-2.2)/0.45)':enable='gte(t,2.2)'[v]"
        )
    fc = dog
    cmd = ["ffmpeg", "-v", "error", "-y"]
    if overlay_logo:
        cmd += ["-loop", "1", "-i", str(endcard)]
    else:
        # 입력 인덱스를 맞추기 위해 더미 없이 intro_motion을 [1]로 두려면 placeholder.
        # overlay_logo=False에서도 필터가 [1:v]를 참조하므로 intro_motion을 [1]에 둔다.
        cmd += ["-f", "lavfi", "-i", "color=c=black:s=16x16:d=1"]
    cmd += ["-i", str(INTRO_MOTION)]
    # intro_motion(Seedance)의 원본 사운드를 그대로 살리고, 로고 등장 시점에
    # 징글 보이스를 그 위에 얹는다 (2026-07-26 사용자 요청 — 모션·소리 유지).
    parts = ["[mot]"]
    fc += ";[1:a]aresample=48000,aformat=channel_layouts=stereo[mot]"
    ai = 2
    if jingle:
        cmd += ["-i", str(jingle)]
        fc += (f";[{ai}:a]loudnorm=I={NARRATION_LUFS}:TP=-1.5:LRA=11,"
               f"adelay={ms}|{ms},apad,atrim=0:{BUMPER_SEC}[jin]")
        parts.append("[jin]"); ai += 1
    if bgm:
        cmd += ["-i", str(bgm)]
        fc += (f";[{ai}:a]atrim=0:{BUMPER_SEC},volume=0.30,afade=t=in:st=0:d=0.5,"
               f"afade=t=out:st={BUMPER_SEC - 0.6}:d=0.6[bed]")
        parts.append("[bed]"); ai += 1
    n = len(parts)
    if n >= 2:
        fc += (f";{''.join(parts)}amix=inputs={n}:normalize=0,"
               "aformat=sample_rates=48000:channel_layouts=stereo[a]")
    else:
        fc += f";{parts[0]}aformat=sample_rates=48000:channel_layouts=stereo[a]"
    cmd += ["-filter_complex", fc, "-map", "[v]", "-map", "[a]",
            "-c:a", "aac", "-b:a", "192k"]
    cmd += ["-t", str(BUMPER_SEC), "-c:v", "libx264", "-crf", "18",
            "-preset", "medium", "-pix_fmt", "yuv420p", str(out)]
    subprocess.run(cmd, check=True)
    return out


def build_thumbnails(headline: str, sub: str, quote: str,
                     out_dir: Path | None = None) -> list[Path]:
    """썸네일 3안 (1280x720). 심리 트랙 전용 문법 — 사연 트랙과 다르다.

    사연 트랙은 흰/노랑/마젠타 고자극 문법이지만, 이 채널의 자산은 신뢰라
    3색(웜크림·잉크·코럴)으로 제한하고 자극 대신 **질문**으로 클릭을 만든다.
    텍스트는 화면의 40% 안쪽, 마스코트가 나머지를 차지한다.

    A 질문형   — 큰 질문 + 깔끔한 마커 마스코트(logo_c)
    B 대사형   — ✕ 말풍선 대사 + 마스코트 (채널의 ✕✓ 문법을 썸네일에 노출)
    C 스케치형 — 거친 스케치 마스코트(logo_b)로 손그림 감성 강조
    """
    out_dir = out_dir or BRAND_DIR / "thumbs"
    out_dir.mkdir(parents=True, exist_ok=True)
    TW, TH = 1280, 720
    black = lambda s: ImageFont.truetype(str(ROOT / "data/assets/fonts/Pretendard-Black.otf"), s)

    def wrap(d, text, font, max_w):
        lines, cur = [], ""
        for w in text.split():
            t = f"{cur} {w}".strip()
            if d.textlength(t, font=font) <= max_w or not cur:
                cur = t
            else:
                lines.append(cur); cur = w
        if cur:
            lines.append(cur)
        return lines

    outs = []
    for tag, mascot_path, kind in (("A", MASCOT, "q"),
                                   ("B", MASCOT, "quote"),
                                   ("C", CHAR_DIR / "logo_b.png", "q")):
        m = Image.open(mascot_path).convert("RGB")
        im = Image.new("RGB", (TW, TH), m.getpixel((4, 4)))
        d = ImageDraw.Draw(im)

        # 마스코트를 크게 — 썸네일은 모바일에서 손톱만 하게 보인다.
        mh = 620
        r = mh / m.height
        ms = m.resize((round(m.width * r), mh), Image.LANCZOS)
        im.paste(ms, (TW - ms.width + 30, TH - mh - 10))

        # 텍스트 블록을 먼저 조판해 전체 높이를 구하고 세로 중앙에 앉힌다
        # (위쪽에만 몰리면 하단이 비어 허전해 보인다).
        if kind == "quote":
            qf, sf = black(56), black(44)
            qls = wrap(d, quote, qf, 560)
            sls = wrap(d, sub, sf, 620)
            bub_h = max(200, 60 + len(qls) * 74)
            total = bub_h + 40 + len(sls) * 58
            y = (TH - total) // 2
            d.rounded_rectangle((44, y, 800, y + bub_h), radius=28, fill=RED_SOFT)
            cy = y + bub_h // 2
            for dx in (0, 3):
                d.line((88 + dx, cy - 38, 144 + dx, cy + 38), fill=(214, 69, 65), width=12)
                d.line((144 + dx, cy - 38, 88 + dx, cy + 38), fill=(214, 69, 65), width=12)
            ty = y + (bub_h - len(qls) * 74) // 2
            for ln in qls:
                d.text((180, ty), ln, font=qf, fill=INK)
                ty += 74
            y += bub_h + 40
            for ln in sls:
                d.text((48, y), ln, font=sf, fill=CORAL)
                y += 58
        else:
            hf, sf = black(80), black(46)
            hls = wrap(d, headline, hf, 640)
            sls = wrap(d, sub, sf, 620)
            total = len(hls) * 100 + 46 + len(sls) * 60
            y = (TH - total) // 2
            for ln in hls:
                d.text((48, y), ln, font=hf, fill=INK)
                y += 100
            d.line((52, y + 18, 240, y + 18), fill=CORAL, width=10)
            y += 46
            for ln in sls:
                d.text((48, y), ln, font=sf, fill=CORAL)
                y += 60

        p = out_dir / f"thumb_{tag}.png"
        im.save(p)
        outs.append(p)
    return outs


def insert_bumper(episode: Path, at: float, out: Path | None = None) -> Path:
    """에피소드의 `at`초 지점에 범퍼를 끼워 넣는다 (훅 직후).

    구현 주의 — **split 쓰지 말 것.** `[0:v]split=2`로 앞/뒤를 나누면 concat이
    앞부분을 소비하는 동안 뒤쪽 분기가 영상 **전체를 메모리에 버퍼링**한다.
    카드만 있는 20MB 영상은 버티지만 실사 스톡이 섞여 50MB가 되면 중간에 끊겨
    10분짜리가 5분으로 잘려 나온다(실제로 겪음). 대신 **같은 파일을 -ss/-t로
    두 번 입력**하면 각 입력이 독립적으로 시킹해 버퍼링이 아예 없다.

    오디오 규격도 맞춘다(에피소드 44.1k 모노 vs 범퍼 48k 스테레오).
    setsar=1은 실사 세그먼트(SAR 1:1)와 카드 세그먼트(SAR 미설정) 혼재 대비.
    """
    out = out or episode.with_name("episode_intro.mp4")
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries",
         "stream=sample_rate,channels", "-of", "csv=p=0", str(episode)],
        capture_output=True, text=True, check=True).stdout.strip().split(",")
    rate, ch = probe[0], "mono" if probe[1] == "1" else "stereo"

    # 정확히 `at`에서 자른다 — 키프레임(-c copy)은 씬 경계에서 최대 GOP만큼
    # 어긋나, 범퍼 앞에 다음 씬 카드가 0.1초 깜빡이는 사고가 났다(2026-07-26).
    # 세 조각 모두 같은 규격으로 재인코딩해 concat한다(경계 프레임 정확).
    tmp = out.parent / "work" / "bumper_join"
    tmp.mkdir(parents=True, exist_ok=True)
    p1, p2 = tmp / "p1.mp4", tmp / "p2.mp4"
    bn = tmp / "bumper_norm.mp4"
    venc = ["-c:v", "libx264", "-crf", "18", "-preset", "veryfast",
            "-pix_fmt", "yuv420p"]
    aenc = ["-c:a", "aac", "-b:a", "192k", "-ar", str(rate)]
    vf_scale = "scale=1920:1080,setsar=1,fps=30"

    # -t / -ss 를 -i 뒤(출력측)에 둔다 = 프레임 정확 (입력측 -ss는 키프레임 fast
    # seek이라 경계가 어긋난다). p1은 정확히 at에서 끝나고 p2는 정확히 at에서 시작.
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(episode),
                    "-t", f"{at:.3f}", "-vf", vf_scale, *venc, *aenc,
                    "-af", f"aformat=channel_layouts={ch}", str(p1)], check=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(episode),
                    "-ss", f"{at:.3f}", "-vf", vf_scale, *venc, *aenc,
                    "-af", f"aformat=channel_layouts={ch}", str(p2)], check=True)
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-i", str(BUMPER),
         "-vf", vf_scale, "-af", f"aformat=sample_rates={rate}:channel_layouts={ch}",
         *venc, *aenc, str(bn)], check=True)

    # 경계를 크로스페이드(디졸브)로 잇는다 — 하드 컷이 "갑자기 전환"으로 어색하다는
    # 피드백(2026-07-26). 앞/뒤 0.4s씩 겹쳐 부드럽게 넘어간다.
    xf = 0.4
    off1 = at - xf
    off2 = at + BUMPER_SEC - 2 * xf
    graph = (
        f"[0:v][1:v]xfade=transition=fade:duration={xf}:offset={off1:.3f}[vx1];"
        f"[vx1][2:v]xfade=transition=fade:duration={xf}:offset={off2:.3f}[v];"
        f"[0:a][1:a]acrossfade=d={xf}[ax1];"
        f"[ax1][2:a]acrossfade=d={xf}[a]"
    )
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(p1), "-i", str(bn),
                    "-i", str(p2), "-filter_complex", graph, "-map", "[v]", "-map", "[a]",
                    *venc, "-preset", "medium", *aenc, str(out)], check=True)
    got = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(out)], capture_output=True, text=True, check=True)
    made, src = float(got.stdout), _duration(episode)
    expect = src + BUMPER_SEC - 2 * xf          # 크로스페이드로 겹친 만큼 짧다
    if abs(made - expect) > 1.0:                 # 잘림 사고를 조용히 넘기지 않는다
        raise RuntimeError(
            f"범퍼 삽입 결과 길이 이상: {made:.1f}s (기대 {expect:.1f}s)")
    return out


def mix_global_bgm(video: Path, out: Path | None = None,
                   bgm: Path | None = None,
                   mute: tuple[float, float] | None = None) -> Path:
    """영상 전체(본편)에 연속 BGM 베드를 깐다 (-26 LUFS 언더베드).

    기존 오디오(내레이션+징글)는 그대로 두고 그 아래에 베드만 더한다.
    mute=(start,end)를 주면 그 구간에서만 베드를 뺀다 — 범퍼 구간은 intro_motion의
    자체 사운드+징글로 충분해 베드를 겹치지 않는다(2026-07-26 사용자 요청).
    """
    from core.assemble import BGM_LUFS
    bgm = bgm or BGM_BED
    out = out or video.with_name(video.stem + "_bgm.mp4")
    bed = f"[1:a]loudnorm=I={BGM_LUFS}:TP=-2.0:LRA=7,aresample=44100"
    if mute:
        s, e = mute
        bed += f",volume='if(between(t,{s:.3f},{e:.3f}),0,1)':eval=frame"
    subprocess.run([
        "ffmpeg", "-v", "error", "-y", "-i", str(video),
        "-stream_loop", "-1", "-i", str(bgm), "-filter_complex",
        f"{bed}[bed];"
        "[0:a][bed]amix=inputs=2:duration=first:normalize=0,"
        "alimiter=limit=0.97[a]",
        "-map", "0:v", "-map", "[a]", "-c:v", "copy",
        "-c:a", "aac", "-b:a", "192k", "-shortest", str(out)],
        check=True)
    return out


def _nearest_keyframe(video: Path, t: float, window: float = 4.0) -> float:
    """`t` 부근의 실제 키프레임 시각. 여기서 잘라야 -c copy가 정확하다.

    assemble이 씬별 세그먼트를 이어 붙이므로 씬 경계는 항상 키프레임이다 —
    훅 끝(= 씬 경계)을 넘기면 대개 오차 0.05초 안에 붙는다.
    """
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-skip_frame", "nokey",
         "-show_entries", "frame=best_effort_timestamp_time", "-of", "csv=p=0",
         "-read_intervals", f"{max(0, t - window)}%+{window * 2}", str(video)],
        capture_output=True, text=True, check=True)
    ks = [float(x) for x in r.stdout.replace(",", " ").split() if x]
    return min(ks, key=lambda k: abs(k - t)) if ks else t


def _duration(p: Path) -> float:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "csv=p=0", str(p)], capture_output=True, text=True, check=True)
    return float(r.stdout)


def main() -> None:
    print("1) 로고 카드")
    print(f"   → {build_logo_card()}")
    print("2) 범퍼 (4초, 훅 뒤 삽입용)")
    print(f"   → {build_bumper()}")


if __name__ == "__main__":
    main()
