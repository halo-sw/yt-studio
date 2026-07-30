"""service/api/app.py — 로컬 웹 UI 백엔드 (FastAPI).

실행: python cli.py ui  →  http://127.0.0.1:8787
- 대본 재고/산출물 조회, produce/batch/write 잡 실행, 진행 로그, 지표 시트.
- 로컬 전용(127.0.0.1 바인드). 게이트(승인·업로드 공개 전환)는 여전히 사람.
"""

from __future__ import annotations

import json
import subprocess
import sys
import threading
import uuid
from pathlib import Path

import yaml
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "data" / "scripts"
OUTPUTS = ROOT / "data" / "assets" / "produce"
METRICS = ROOT / "data" / "metrics.json"
UI_INDEX = ROOT / "service" / "web" / "ui" / "index.html"

# 슬러그 → 카테고리 (§A3 5축)
CATEGORY = {
    "phishing": "금전·사기", "junggo": "금전·사기", "yuryubun": "상속",
    "drawer": "직장 반전",
    "gyeongbiwon": "미스터리", "bakery": "미스터리", "delivery": "미스터리",
    "jeonse": "부동산", "gantong": "부동산",
    "milk": "가족·관계",
}

app = FastAPI(title="yt-studio-multi")

# ---------------------------------------------------------------------------
# 잡 러너 — subprocess로 cli.py를 실행하고 로그를 메모리에 축적
# ---------------------------------------------------------------------------

JOBS: dict[str, dict] = {}


def _run_job(job_id: str, args: list[str]) -> None:
    job = JOBS[job_id]
    try:
        proc = subprocess.Popen(
            [sys.executable, "cli.py", *args],
            cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1,
        )
        for line in proc.stdout:
            job["log"].append(line.rstrip())
        proc.wait()
        job["status"] = "done" if proc.returncode == 0 else "failed"
    except Exception as e:  # noqa: BLE001 — 잡 실패는 로그로 보고
        job["log"].append(f"[에러] {type(e).__name__}: {e}")
        job["status"] = "failed"


def _start_job(kind: str, label: str, args: list[str]) -> str:
    job_id = uuid.uuid4().hex[:8]
    JOBS[job_id] = {"id": job_id, "kind": kind, "label": label,
                    "status": "running", "log": []}
    threading.Thread(target=_run_job, args=(job_id, args), daemon=True).start()
    return job_id


# ---------------------------------------------------------------------------
# 상태 조회
# ---------------------------------------------------------------------------

def _queue_titles() -> dict[str, str]:
    titles: dict[str, str] = {}
    for q in SCRIPTS.glob("batch_*.yaml"):
        try:
            for item in yaml.safe_load(q.read_text(encoding="utf-8")) or []:
                titles[Path(item["script"]).stem] = item["title"]
        except Exception:  # noqa: BLE001 — 큐 파일 오류는 무시하고 계속
            continue
    return titles


def _lint(lines: list[str]) -> list[str]:
    from core.schemas import Scene, SceneVisual, Track
    from tracks.recap.style_lint import lint_nyaong

    scenes = [Scene(scene_id=i + 1, track=Track.RECAP, chapter="본편",
                    narration=ln, caption=ln[:30],
                    visual=SceneVisual(type="slide", ref="x"))
              for i, ln in enumerate(lines)]
    return lint_nyaong(scenes)


@app.get("/api/state")
def state() -> dict:
    titles = _queue_titles()
    scripts = []
    for p in sorted(SCRIPTS.glob("*.txt")):
        lines = [ln.strip() for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]
        issues = _lint(lines)
        hook = lines[0] if lines else ""
        facts_path = p.with_suffix(".facts.json")
        if facts_path.exists() and "{{fact:" in hook:
            # 표시용 치환 — 렌더 시에는 tts.resolve_fact_tokens가 정식 처리
            try:
                from core.schemas import FactSheet
                from core.tts import resolve_fact_tokens

                sheet = FactSheet(facts=json.loads(facts_path.read_text(encoding="utf-8")))
                hook = resolve_fact_tokens(hook, sheet)
            except Exception:  # noqa: BLE001 — 표시 실패는 원문 유지
                pass
        scripts.append({
            "slug": p.stem,
            "title": titles.get(p.stem, p.stem),
            "category": CATEGORY.get(p.stem, "—"),
            "lines": len(lines),
            "hook": hook,
            "lint_ok": not issues,
            "lint_issues": issues[:5],
            "has_facts": p.with_suffix(".facts.json").exists(),
            "rendered": (OUTPUTS / p.stem / "episode.mp4").exists(),
        })

    outputs = []
    if OUTPUTS.exists():
        for d in sorted(OUTPUTS.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
            if not d.is_dir():
                continue
            meta = d / "meta.txt"
            outputs.append({
                "slug": d.name,
                "meta": meta.read_text(encoding="utf-8") if meta.exists() else "",
                "episode": (d / "episode.mp4").exists(),
                "shorts": (d / "shorts.mp4").exists(),
                "edit_plan": (d / "edit_plan.json").exists(),
            })

    queues = [q.name for q in sorted(SCRIPTS.glob("batch_*.yaml"))]
    jobs = [{k: v for k, v in j.items() if k != "log"} | {"tail": j["log"][-1] if j["log"] else ""}
            for j in JOBS.values()]
    return {"scripts": scripts, "outputs": outputs, "queues": queues,
            "jobs": list(reversed(jobs))}


# ---------------------------------------------------------------------------
# 잡 실행 API
# ---------------------------------------------------------------------------

class ProduceReq(BaseModel):
    script: str
    title: str
    track: str = "recap"
    shorts: bool = True
    bgm: str = ""


class BatchReq(BaseModel):
    queue: str


class WriteReq(BaseModel):
    topic: str
    slug: str
    title: str = ""
    render: bool = True


@app.post("/api/produce")
def produce(req: ProduceReq) -> dict:
    args = ["produce", "--script", req.script, "--title", req.title,
            "--track", req.track]
    if req.shorts:
        args.append("--shorts")
    if req.bgm:
        args += ["--bgm", req.bgm]
    return {"job": _start_job("produce", req.title, args)}


@app.post("/api/batch")
def batch(req: BatchReq) -> dict:
    q = SCRIPTS / req.queue
    if not q.exists():
        raise HTTPException(404, f"큐 없음: {req.queue}")
    return {"job": _start_job("batch", req.queue, ["batch", "--queue", str(q)])}


@app.post("/api/write")
def write(req: WriteReq) -> dict:
    args = ["write", "--topic", req.topic, "--slug", req.slug]
    if req.title:
        args += ["--title", req.title]
    if req.render:
        args.append("--render")
    return {"job": _start_job("write", req.slug, args)}


@app.get("/api/jobs/{job_id}")
def job_detail(job_id: str) -> dict:
    if job_id not in JOBS:
        raise HTTPException(404, "잡 없음")
    return JOBS[job_id]


# ---------------------------------------------------------------------------
# 부동산 트랙 — 예린이의 부동산 뽀개기 (후보 조회 + 원커맨드 에피소드)
# ※ 신규 화면: 3인 합의 대상 (CLAUDE.md 10장) — 합의 전까지 파일럿 탭
# ---------------------------------------------------------------------------

class ReEpisodeReq(BaseModel):
    home_code: str
    name: str = ""
    videos: bool = False       # 공식 투어 영상 조회·프레임 캡처 포함
    skip_assets: bool = False  # 기존 수집 에셋 재사용
    reuse_audio: bool = False  # 기존 TTS 재사용 (재렌더)


@app.get("/api/realestate/candidates")
def realestate_candidates(top: int = 20) -> list:
    """청년안심주택 후보 목록 (빠른 추출 — 영상 조회는 에피소드 생성 시 옵션)."""
    from tracks.realestate import parser as re_parser

    try:
        complexes = re_parser.load_complexes()
    except FileNotFoundError as e:
        raise HTTPException(500, f"데이터 폴더 없음 — .env REALESTATE_DATA_DIR 확인: {e}")
    out = []
    for c in re_parser.extract_candidates(complexes, top_n=top):
        out.append({
            "home_code": c.home_code, "name": c.name, "gu": c.gu,
            "address": c.address, "subway": c.subway,
            "station_m": c.station_distance_m(),
            "deposit_low_won": c.deposit_low_won, "rent_low_won": c.rent_low_won,
            "total_units": c.total_units, "has_homepage": bool(c.homepage),
            "score": c.score,
            "rendered": (OUTPUTS / f"re-{c.home_code}" / "episode.mp4").exists(),
            "has_assets": (ROOT / "data" / "assets" / "realestate" / c.home_code / "assets.json").exists(),
        })
    return out


@app.post("/api/realestate/sync")
def realestate_sync() -> dict:
    """매물 데이터 자체 수집 잡 — 청년안심주택 포털 → data/realestate/complexes.json."""
    return {"job": _start_job("re-sync", "매물 데이터 수집", ["re-sync"])}


@app.post("/api/realestate/episode")
def realestate_episode(req: ReEpisodeReq) -> dict:
    """후보 하나 → 에셋 수집 → 덱 → 슬라이드 → 대본 → 렌더 (cli re-episode 잡)."""
    args = ["re-episode", "--home-code", req.home_code]
    if req.videos:
        args.append("--videos")
    if req.skip_assets:
        args.append("--skip-assets")
    if req.reuse_audio:
        args.append("--reuse-audio")
    return {"job": _start_job("re-episode", req.name or req.home_code, args)}


# ---------------------------------------------------------------------------
# 지표 시트 (§B8 — harvest 구현 전 수동 기록)
# ---------------------------------------------------------------------------

class MetricRow(BaseModel):
    slug: str
    date: str
    views24: int = 0
    views7d: int = 0
    completion: float = 0.0
    subs: int = 0


@app.get("/api/metrics")
def metrics_get() -> list:
    if METRICS.exists():
        return json.loads(METRICS.read_text(encoding="utf-8"))
    return []


@app.post("/api/metrics")
def metrics_add(row: MetricRow) -> dict:
    rows = metrics_get()
    rows = [r for r in rows if not (r["slug"] == row.slug and r["date"] == row.date)]
    rows.append(row.model_dump() | {"category": CATEGORY.get(row.slug, "—")})
    METRICS.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    return {"ok": True, "rows": len(rows)}


# ---------------------------------------------------------------------------
# 정적 서빙 — UI + 영상 미리보기
# ---------------------------------------------------------------------------

@app.get("/")
def index() -> FileResponse:
    return FileResponse(UI_INDEX)


@app.get("/realestate")
def realestate_page() -> FileResponse:
    """부동산 전용 제작 스튜디오 — 매물 선택→제작→완성 흐름만 담은 독립 화면."""
    return FileResponse(UI_INDEX.parent / "realestate.html")


app.mount("/media", StaticFiles(directory=ROOT / "data" / "assets"), name="media")
