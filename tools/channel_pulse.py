"""채널 현황 배치 — data/channels.yaml의 채널들을 yt-dlp로 스냅샷.

실행: .venv/bin/python tools/channel_pulse.py
산출: data/usage/channel_pulse.jsonl에 채널당 1줄 append + 콘솔 요약(직전 대비 증감).
API 키 불요(공개 페이지 스크랩). 실패한 채널은 건너뛰고 나머지는 계속한다.
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CHANNELS = ROOT / "data" / "channels.yaml"
LEDGER = ROOT / "data" / "usage" / "channel_pulse.jsonl"
YTDLP = Path(sys.executable).parent / "yt-dlp"


def snapshot(url: str) -> dict:
    out = subprocess.run(
        [str(YTDLP), "--flat-playlist", "--dump-single-json", url.rstrip("/") + "/videos"],
        capture_output=True, text=True, timeout=120,
    )
    if out.returncode != 0:
        raise RuntimeError(out.stderr.strip().splitlines()[-1] if out.stderr else "yt-dlp 실패")
    d = json.loads(out.stdout)
    return {
        "name": d.get("channel") or d.get("title"),
        "followers": d.get("channel_follower_count"),
        "videos": [
            {
                "id": e.get("id"),
                "title": e.get("title"),
                "views": e.get("view_count"),
                "duration": e.get("duration"),
            }
            for e in d.get("entries", [])
        ],
    }


def last_snapshot(track: str) -> dict | None:
    if not LEDGER.exists():
        return None
    latest = None
    for line in LEDGER.read_text().splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get("track") == track:
            latest = row
    return latest


def fmt_delta(now: int | None, before: int | None) -> str:
    if now is None:
        return "?"
    if before is None:
        return f"{now:,}"
    diff = now - before
    sign = f" ({diff:+,})" if diff else ""
    return f"{now:,}{sign}"


def main() -> int:
    channels = yaml.safe_load(CHANNELS.read_text())
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    failures = []

    for track, info in channels.items():
        if not info or not info.get("url"):
            continue
        try:
            snap = snapshot(info["url"])
        except Exception as e:  # noqa: BLE001 — 한 채널 실패가 배치를 죽이면 안 됨
            failures.append(f"{track}: {e}")
            continue
        prev = last_snapshot(track)
        row = {"ts": ts, "track": track, **snap}
        with LEDGER.open("a") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

        prev_views = {v["id"]: v.get("views") for v in (prev or {}).get("videos", [])}
        print(f"\n[{track}] {snap['name']} — 구독 {fmt_delta(snap['followers'], (prev or {}).get('followers'))}"
              f" · 영상 {len(snap['videos'])}개")
        for v in snap["videos"][:10]:
            title = (v["title"] or "")[:40]
            print(f"  - {title} | 조회 {fmt_delta(v.get('views'), prev_views.get(v['id']))}")

    if failures:
        print("\n[실패]", *failures, sep="\n  ")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
