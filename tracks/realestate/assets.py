"""부동산 — 에피소드 비주얼 에셋 수집기.

소재 카드 확정 후, 후보 단지의 좌표·공식 영상으로부터 씬에 쓸 에셋을 수집한다:
- 카카오맵 로드뷰 3컷 (정면 / 외관 올려다보기 / 반대 방향)
- 카카오맵 지도 2컷 (근접 마커 / 광역 + 위치 링)
- 공식 투어 영상 프레임 N컷 (내부 컷 — 로드뷰가 못 보는 안쪽)

캡처는 tracks/realestate/js/의 puppeteer 러너(node)로 수행한다.
수동 대기열(MJ/Higgsfield)과 달리 전부 자동 — 공개 지도/공식 영상 소스만 쓴다.

산출물: data/assets/realestate/{slug}/ 하위 PNG/JPG + assets.json (씬 visual.ref 목록)
"""

from __future__ import annotations

import json
import pathlib
import re
import subprocess
import urllib.parse

from PIL import Image, ImageDraw

from tracks.realestate.parser import Candidate

JS_DIR = pathlib.Path(__file__).parent / "js"
DEFAULT_OUT_ROOT = pathlib.Path("data/assets/realestate")

# 캡처 원본은 1600x1000. 카카오맵 좌측 사이드바 폭 390px.
_SIDEBAR_W = 390
_TOUR_TIMESTAMPS = (8, 25, 45, 132)  # 기본 샘플 시점 (초) — 인트로/중반/후반


class CaptureError(RuntimeError):
    pass


def _ensure_node_deps() -> None:
    if not (JS_DIR / "node_modules").exists():
        try:
            subprocess.run(
                ["npm", "install", "--no-fund", "--no-audit"],
                cwd=JS_DIR, check=True, capture_output=True, timeout=180,
            )
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired) as e:
            raise CaptureError(
                "node/npm 필요 — tracks/realestate/js 에서 `npm install` 실패"
            ) from e


def _node(script: str, *args: str, timeout: int = 120) -> str:
    _ensure_node_deps()
    try:
        r = subprocess.run(
            ["node", str(JS_DIR / script), *args],
            cwd=JS_DIR, check=True, capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.CalledProcessError as e:
        raise CaptureError(f"{script} 실패: {e.stderr[-500:]}") from e
    return r.stdout


def _parse_final_url(stdout: str) -> dict[str, str]:
    m = re.search(r"finalUrl (\S+)", stdout)
    if not m:
        return {}
    q = urllib.parse.urlparse(m.group(1)).query
    return {k: v[0] for k, v in urllib.parse.parse_qs(q).items()}


# ---------------------------------------------------------------------------
# 로드뷰 / 지도
# ---------------------------------------------------------------------------

def capture_roadview_set(lat: float, lng: float, out_dir: pathlib.Path) -> dict:
    """로드뷰 3컷. 첫 컷의 finalUrl에서 panoid/urlX/urlY/pan을 회수해 각도 변주."""
    out_dir = out_dir.resolve()  # node 러너는 js/에서 실행 — 절대경로 필수
    out_dir.mkdir(parents=True, exist_ok=True)
    shots: dict[str, str] = {}

    default = out_dir / "rv_front.png"
    stdout = _node("capture.js", f"https://map.kakao.com/link/roadview/{lat},{lng}",
                   str(default), "10000")
    shots["front"] = str(default)
    params = _parse_final_url(stdout)

    panoid = params.get("panoid")
    if panoid:
        base_pan = float(params.get("pan", "0"))
        urlx, urly = params.get("urlX", "0"), params.get("urlY", "0")

        def rv_url(pan: float, tilt: float) -> str:
            return (
                f"https://map.kakao.com/?panoid={panoid}&pan={pan:.1f}&tilt={tilt}"
                f"&zoom=-1&map_type=TYPE_MAP&map_attribute=ROADVIEW&urlX={urlx}&urlY={urly}"
            )

        tower = out_dir / "rv_tower.png"
        _node("capture.js", rv_url(base_pan, -35), str(tower), "9000")
        shots["tower"] = str(tower)

        reverse = out_dir / "rv_street.png"
        _node("capture.js", rv_url((base_pan + 180) % 360, 0), str(reverse), "9000")
        shots["street"] = str(reverse)

    return {"shots": shots, "params": params}


def _crop_sidebar(src: pathlib.Path, dst: pathlib.Path) -> None:
    im = Image.open(src)
    im.crop((_SIDEBAR_W, 0, im.width, im.height)).save(dst)


def capture_map_set(
    lat: float, lng: float, name: str, out_dir: pathlib.Path,
    urlx: str | None = None, urly: str | None = None,
) -> dict[str, str]:
    """지도 2컷: 근접(마커+정보창) / 광역(위치 링). 광역은 roadview 캡처의 urlX/urlY 필요."""
    out_dir = out_dir.resolve()  # node 러너는 js/에서 실행 — 절대경로 필수
    out_dir.mkdir(parents=True, exist_ok=True)
    shots: dict[str, str] = {}

    close_raw = out_dir / "_map_close_raw.png"
    close = out_dir / "map_close.png"
    _node("capture.js",
          f"https://map.kakao.com/link/map/{urllib.parse.quote(name)},{lat},{lng}",
          str(close_raw), "9000")
    _crop_sidebar(close_raw, close)
    close_raw.unlink(missing_ok=True)
    shots["close"] = str(close)

    if urlx and urly:
        wide_raw = out_dir / "_map_wide_raw.png"
        wide = out_dir / "map_wide.png"
        _node("capture.js",
              f"https://map.kakao.com/?urlX={urlx}&urlY={urly}&urlLevel=7&map_type=TYPE_MAP",
              str(wide_raw), "9000")
        _crop_sidebar(wide_raw, wide)
        wide_raw.unlink(missing_ok=True)
        # 카카오맵은 urlX/urlY를 '사이드바 제외 지도 영역'의 중앙에 놓는다
        # → 사이드바(390px)를 크롭한 이미지에서는 정확히 가로 중앙.
        im = Image.open(wide).convert("RGB")
        d = ImageDraw.Draw(im)
        x, y = im.width // 2, im.height // 2
        d.ellipse([x - 48, y - 48, x + 48, y + 48], outline=(230, 50, 50), width=6)
        d.ellipse([x - 12, y - 12, x + 12, y + 12], fill=(230, 50, 50))
        im.save(wide)
        shots["wide"] = str(wide)

    return shots


# ---------------------------------------------------------------------------
# 공식 투어 영상 프레임
# ---------------------------------------------------------------------------

def _trim_letterbox(path: pathlib.Path) -> None:
    """상하 레터박스(검은 띠) 제거. 행 최대 밝기 30 이하를 띠로 간주."""
    im = Image.open(path).convert("RGB")
    gray = im.convert("L")
    rows = [y for y in range(gray.height)
            if gray.crop((0, y, gray.width, y + 1)).getextrema()[1] > 30]
    if rows and (rows[0] > 0 or rows[-1] < gray.height - 1):
        im.crop((0, rows[0], im.width, rows[-1] + 1)).save(path)


def capture_tour_frames(
    video_id: str, out_dir: pathlib.Path,
    timestamps: tuple[int, ...] = _TOUR_TIMESTAMPS,
) -> list[str]:
    """공식 투어 영상에서 시점별 프레임 캡처. 시점당 새 브라우저 세션(프레임 갱신 이슈)."""
    out_dir = out_dir.resolve()  # node 러너는 js/에서 실행 — 절대경로 필수
    out_dir.mkdir(parents=True, exist_ok=True)
    frames = []
    for t in timestamps:
        out = out_dir / f"tour_{t:03d}s.png"
        _node("yt_frames.js", video_id, str(t), str(out), timeout=90)
        _trim_letterbox(out)
        frames.append(str(out))
    return frames


# ---------------------------------------------------------------------------
# 오케스트레이터
# ---------------------------------------------------------------------------

def collect_assets(
    candidate: Candidate,
    out_root: pathlib.Path = DEFAULT_OUT_ROOT,
) -> dict:
    """후보 단지의 에셋 일괄 수집 → assets.json 기록.

    반환 dict의 visuals는 씬 JSON의 visual(type/ref/effect) 후보 목록이다.
    수치는 담지 않는다 — 수치는 parser.build_fact_sheet()가 단일 출처 (규칙 5-3).
    """
    if not (candidate.lat and candidate.lng):
        raise CaptureError(f"{candidate.name}: 좌표 없음 — 로드뷰/지도 캡처 불가")
    slug = candidate.home_code or re.sub(r"\s+", "_", candidate.name)
    out_dir = pathlib.Path(out_root) / slug

    rv = capture_roadview_set(candidate.lat, candidate.lng, out_dir)
    params = rv["params"]
    maps = capture_map_set(
        candidate.lat, candidate.lng, candidate.name, out_dir,
        urlx=params.get("urlX"), urly=params.get("urlY"),
    )
    frames: list[str] = []
    if candidate.video and candidate.video.relevant:
        frames = capture_tour_frames(candidate.video.video_id, out_dir)

    visuals = (
        [{"type": "slide", "ref": p, "effect": "kenburns"} for p in rv["shots"].values()]
        + [{"type": "slide", "ref": p, "effect": "zoom_callout"} for p in maps.values()]
        + [{"type": "slide", "ref": p, "effect": "kenburns"} for p in frames]
    )
    manifest = {
        "home_code": candidate.home_code,
        "name": candidate.name,
        "roadview": rv["shots"],
        "maps": maps,
        "tour_frames": frames,
        "tour_video_id": candidate.video.video_id if candidate.video else None,
        "visuals": visuals,
    }
    with open(out_dir / "assets.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    return manifest
