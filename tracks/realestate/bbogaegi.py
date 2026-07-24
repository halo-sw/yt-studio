"""공고 뽀개기 하네스 — 에피소드 YAML 하나로 발행 산출물까지 원샷.

사용: python cli.py bbogaegi --episode data/episodes/<slug>.yaml [--skip-visuals]

단계 (모두 멱등 — 산출물이 있으면 건너뜀):
  1. 브랜드 에셋 검증/재생성 (tracks/realestate/brand.py)
  2. 실사 컷(KREAL)·문서 컷(KDOC)·모션 클립 생성 (Higgsfield, 기존 파일 스킵)
  3. 모션 클립 팔린드롬 연장 (재생 후 정지 금지 규칙)
  4. 진행자 인사 씬 = 프레젠터 체인 트림 (추가 크레딧 0)
  5. 슬라이드 렌더 (tracks/realestate/slides.py)
  6. cli produce (TTS는 audio/ 있으면 --reuse-audio 자동)
  7. 분할 레이아웃 + 인트로 범퍼 합성 → episode_presenter.mp4
  8. 썸네일 3안 → thumbs/
  9. upload.txt 타임스탬프 갱신 (없으면 스켈레톤 생성)
 10. cli release

에피소드 YAML 스키마는 data/episodes/changneung.yaml 참조.
"""
from __future__ import annotations

import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import yaml

from tracks.realestate import brand, slides

ROOT = Path(__file__).resolve().parents[2]
PY = sys.executable

KREAL_STYLE = (
    "Hyper-realistic candid documentary photograph taken in South Korea, like a "
    "Korean photojournalism image from a news agency, shot on a full-frame DSLR, "
    "natural ambient light, true-to-life muted colors, slight handheld "
    "imperfection, authentic everyday Korean details. Not cinematic staging, "
    "not illustration, not 3D, no text, no letters, no watermark. "
)
KDOC_STYLE = (
    "Hyper-realistic candid documentary photograph taken in South Korea, shot on "
    "a full-frame DSLR, natural ambient light, true-to-life muted colors. "
    "The paperwork is a modern Korean printed legal document: white A4 pages of "
    "dense printed KOREAN HANGUL text and tables, softly blurred by shallow "
    "focus so the text is not readable. Strictly no Chinese characters, no "
    "Japanese, no Latin letters. Not cinematic staging, no watermark. "
)


def _run(cmd: list[str], **kw) -> None:
    print("   $", " ".join(str(c) for c in cmd)[:160], flush=True)
    subprocess.run([str(c) for c in cmd], check=True, cwd=ROOT, **kw)


def _ffmpeg(args: list) -> None:
    _run(["ffmpeg", "-y", "-v", "error", *args])


# ---------------------------------------------------------------------------
# 2~5) 비주얼
# ---------------------------------------------------------------------------

def build_visuals(ep: dict, vis: Path, skip_gen: bool = False) -> None:
    from core.visuals.higgsfield_gen import gen_image, gen_motion

    photos = {int(k): v for k, v in (ep["scenes"].get("photos") or {}).items()}
    docs = {int(k): v for k, v in (ep["scenes"].get("docs") or {}).items()}
    motions = {int(k): v for k, v in (ep["scenes"].get("motions") or {}).items()}

    if not skip_gen:
        def make_img(item):
            sid, desc = item
            style = KDOC_STYLE if sid in docs else KREAL_STYLE
            ok = gen_image(desc, vis / f"{sid:02d}.png", style=style)
            print(f"   IMG {sid:02d} {'OK' if ok else 'FAIL'}", flush=True)

        todo = [(s, p) for s, p in {**photos, **docs}.items()
                if not (vis / f"{s:02d}.png").exists()]
        if todo:
            with ThreadPoolExecutor(max_workers=3) as ex:
                list(ex.map(make_img, todo))

        def make_mot(item):
            sid, desc = item
            ok = gen_motion(vis / f"{sid:02d}.png", desc, vis / f"{sid:02d}.mp4")
            print(f"   MOT {sid:02d} {'OK' if ok else 'FAIL'}", flush=True)

        todo_m = [(s, m) for s, m in motions.items()
                  if (vis / f"{s:02d}.png").exists()
                  and not (vis / f"{s:02d}.mp4").exists()]
        if todo_m:
            with ThreadPoolExecutor(max_workers=3) as ex:
                list(ex.map(make_mot, todo_m))

    # 팔린드롬 연장 (정+역 concat 후 loop — "재생 후 정지" 어색함 제거)
    for sid in motions:
        mp4 = vis / f"{sid:02d}.mp4"
        marker = vis / f"{sid:02d}.pal"
        if mp4.exists() and not marker.exists():
            tmp = vis / f"{sid:02d}.pal.mp4"
            _ffmpeg(["-i", mp4, "-filter_complex",
                     "[0:v]fps=30,split[a][b];[b]reverse[r];[a][r]concat=n=2:v=1:a=0,"
                     "loop=loop=1:size=32767[v]", "-map", "[v]", "-an", tmp])
            tmp.replace(mp4)
            marker.write_text("palindromized")

    # 진행자 인사 씬: 체인 앞부분 트림 → 메인에서 말하는 컷 (크레딧 0)
    psc = ep["scenes"].get("presenter_scene")
    if psc and not (vis / f"{int(psc):02d}.mp4").exists():
        _ffmpeg(["-i", brand.PRESENTER_CHAIN, "-t", "24", "-c", "copy",
                 vis / f"{int(psc):02d}.mp4"])
        (vis / f"{int(psc):02d}.pal").write_text("from-chain")

    # 슬라이드
    for sid, spec in (ep["scenes"].get("slides") or {}).items():
        slides.render_slide(spec, vis / f"{int(sid):02d}.png", vis)


# ---------------------------------------------------------------------------
# 6) produce / 7) 합성
# ---------------------------------------------------------------------------

def run_produce(ep: dict, vis: Path, workdir: Path) -> None:
    slide_ids = ",".join(str(s) for s in sorted(int(k) for k in (ep["scenes"].get("slides") or {})))
    cmd = [PY, "cli.py", "produce", "--script", ep["script"], "--title", ep["title"],
           "--track", "realestate", "--images", str(vis), "--slug", ep["slug"]]
    if slide_ids:
        cmd += ["--static", slide_ids]
    if (workdir / "audio").exists():
        cmd.append("--reuse-audio")
    _run(cmd)


def scene_marks(workdir: Path) -> dict[int, float]:
    plan = json.loads((workdir / "edit_plan.json").read_text())
    t, marks = 0.0, {}
    for s in plan["scenes"]:
        marks[s["scene_id"]] = round(t, 2)
        t += s.get("duration", 0)
    marks[0] = round(t, 2)  # total
    return marks


def compose_layout(ep: dict, workdir: Path) -> Path:
    """분할 레이아웃 + 범퍼 삽입.

    ffmpeg 함정 (2026-07-24 실측): ① 무한 소스(color/stream_loop)는 d=·trim·-t로
    종료를 명시하지 않으면 무한 인코딩 ② 같은 라벨을 두 번 소비하면 일부 구간에
    필터가 안 먹는다 — split/asplit 필수.
    """
    assets = brand.ensure_brand_assets()
    marks = scene_marks(workdir)
    total = marks[0]
    cut = marks[2]                       # 범퍼 위치 = 훅(씬1) 직후
    psc = int(ep["scenes"].get("presenter_scene", 0))
    hide = (marks.get(psc, 0), marks.get(psc + 1, 0)) if psc else (0, 0)
    mw, mh = brand.MAIN_SIZE
    mx, my = brand.MAIN_POS
    cw, ch = brand.CAM_SIZE
    cx, cy = brand.CAM_POS
    out = workdir / "episode_presenter.mp4"
    loops = int(total // 35) + 2
    en = f"not(between(t,{hide[0]},{hide[1]}))"
    graph = (
        f"color=c={brand.CANVAS_COLOR}:s=1920x1080:r=30:d={total}[bg];"
        f"[0:v]scale={mw}:{mh},setsar=1[main];[bg][main]overlay={mx}:{my}:shortest=1[b1];"
        f"[2:v]trim=0:{total + 1},scale={cw}:{ch},setsar=1,format=rgba[cv];"
        f"[3:v]format=gray[cm];[cv][cm]alphamerge[cam];"
        f"[b1][cam]overlay={cx}:{cy}:shortest=1:enable='{en}'[b2];"
        f"[b2][4:v]overlay={cx - 5}:{cy - 5}:enable='{en}'[b3];"
        f"[b3][5:v]overlay={brand.LOGO_CARD_POS[0]}:{brand.LOGO_CARD_POS[1]}[lay];"
        f"[lay]split[layA][layB];"
        f"[layA]trim=0:{cut},setpts=PTS-STARTPTS[v1];"
        f"[layB]trim={cut},setpts=PTS-STARTPTS[v2];"
        f"[0:a]asplit[aA][aB];"
        f"[aA]atrim=0:{cut},asetpts=PTS-STARTPTS,aformat=sample_rates=44100:channel_layouts=stereo[a1];"
        f"[aB]atrim={cut},asetpts=PTS-STARTPTS,aformat=sample_rates=44100:channel_layouts=stereo[a2];"
        f"[1:v]fps=30,setsar=1[bv];[1:a]aformat=sample_rates=44100:channel_layouts=stereo[ba];"
        f"[v1][a1][bv][ba][v2][a2]concat=n=3:v=1:a=1[v][a]"
    )
    _ffmpeg(["-i", workdir / "episode.mp4", "-i", assets["bumper"],
             "-stream_loop", str(loops), "-i", assets["chain"],
             "-i", assets["cam_mask"], "-i", assets["cam_ring"], "-i", assets["logo_card"],
             "-filter_complex", graph, "-map", "[v]", "-map", "[a]",
             "-t", str(total + brand.BUMPER_SEC + 0.5),
             "-c:v", "libx264", "-crf", "21", "-preset", "veryfast",
             "-maxrate", "10M", "-bufsize", "20M", "-c:a", "aac", "-b:a", "192k", out])
    return out


# ---------------------------------------------------------------------------
# 8) 썸네일 / 9) 타임스탬프 / 10) 릴리스
# ---------------------------------------------------------------------------

def build_thumbs(ep: dict, vis: Path, workdir: Path) -> None:
    from PIL import Image, ImageDraw, ImageFilter, ImageFont
    out = workdir / "thumbs"
    out.mkdir(parents=True, exist_ok=True)
    W, H = 1280, 720
    font = str(brand.FONT_PATH)

    def txt(d, xy, s, size, fill, anchor):
        f = ImageFont.truetype(font, size)
        d.text(xy, s, font=f, fill=fill, anchor=anchor,
               stroke_width=max(4, size // 18), stroke_fill=(15, 15, 15))

    for name, spec in (ep.get("thumbs") or {}).items():
        src = vis / f"{int(spec['base']):02d}.png"
        im = Image.open(src).convert("RGB")
        r = max(W / im.width, H / im.height)
        im = im.resize((round(im.width * r), round(im.height * r)), Image.LANCZOS)
        im = im.crop(((im.width - W) // 2, (im.height - H) // 2,
                      (im.width - W) // 2 + W, (im.height - H) // 2 + H))
        side = spec.get("side", "left")
        grad = Image.new("L", (W, 1), 0)
        for x in range(W):
            t = x / W if side == "right" else 1 - x / W
            grad.putpixel((x, 0), int(170 * max(0.0, t - 0.35) / 0.65))
        grad = grad.resize((W, H)).filter(ImageFilter.GaussianBlur(2))
        im = Image.composite(Image.new("RGB", (W, H), (8, 8, 12)), im, grad)
        d = ImageDraw.Draw(im)
        x = W - 48 if side == "right" else 48
        anchor = "ra" if side == "right" else "la"
        txt(d, (x, 150), spec["l1"], 84, (255, 255, 255), anchor)
        txt(d, (x, 255), spec["l2"], 132, (255, 210, 40), anchor)
        txt(d, (x, 430), spec.get("sub", ""), 54, (235, 235, 235), anchor)
        im.save(out / f"{name}.png")
        print(f"   thumb {name} OK", flush=True)


def write_timestamps(ep: dict, workdir: Path) -> str:
    marks = scene_marks(workdir)
    cut = marks[2]

    def fmt(sec):
        m, s = divmod(round(sec), 60)
        return f"{m:02d}:{s:02d}"

    chapters = {int(k): v for k, v in (ep.get("chapters") or {}).items()}
    lines = ["⏱ 타임스탬프", "00:00 " + chapters.get(1, "훅"), f"{fmt(cut)} 채널 인트로"]
    for sid in sorted(chapters):
        if sid == 1:
            continue
        t = marks[sid] + (brand.BUMPER_SEC if marks[sid] >= cut else 0)
        lines.append(f"{fmt(t)} {chapters[sid]}")
    block = "\n".join(lines)
    up = workdir / "upload.txt"
    if up.exists():
        import re
        src = up.read_text()
        if "⏱ 타임스탬프" in src:
            src = re.sub(r"⏱ 타임스탬프\n(?:[0-9]{2}:[0-9]{2} .*\n?)*", block + "\n", src, count=1)
        else:
            src += "\n" + block + "\n"
        up.write_text(src)
    else:
        up.write_text(f"[제목]\n{ep['title']}\n\n{block}\n\n"
                      f"[채널] {brand.CHANNEL_NAME} — {brand.TAGLINE}\n"
                      "※ 설명란·태그·수익창출 체크리스트는 직전 에피소드 upload.txt를 복제해 채울 것\n")
    return block


def run(episode_yaml: str | Path, skip_visuals: bool = False) -> None:
    ep = yaml.safe_load(Path(episode_yaml).read_text(encoding="utf-8"))
    slug = ep["slug"]
    vis = ROOT / f"data/assets/produce/{slug}_vis"
    workdir = ROOT / f"data/assets/produce/{slug}"
    vis.mkdir(parents=True, exist_ok=True)

    print(f"[공고 뽀개기] {slug} — {ep['title']}")
    print("1) 브랜드 에셋")
    brand.ensure_brand_assets()
    print("2~5) 비주얼 (실사·모션·팔린드롬·인사 씬·슬라이드)")
    build_visuals(ep, vis, skip_gen=skip_visuals)
    print("6) produce (TTS+렌더)")
    run_produce(ep, vis, workdir)
    print("7) 분할 레이아웃 + 인트로 합성")
    compose_layout(ep, workdir)
    print("8) 썸네일")
    build_thumbs(ep, vis, workdir)
    print("9) 타임스탬프")
    print(write_timestamps(ep, workdir))
    print("10) 릴리스")
    _run([PY, "cli.py", "release", "--slug", slug,
          "--video", str(workdir / "episode_presenter.mp4")])
    print(f"완료 → data/releases/{slug}/")
