"""유튜브 레퍼런스 영상 저장 — 분석용 로컬 아카이브.

실행: .venv/bin/python tools/save_video.py <URL> [슬러그]
산출: data/assets/reference/<슬러그>/ 에 영상(mp4)+자막(ko/en)+메타(info.json).
nexusshell.kr과 동일 엔진(yt-dlp)을 직접 사용 — 서버 경유 없이 같은 결과.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "assets" / "reference"
YTDLP = Path(sys.executable).parent / "yt-dlp"


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    url = sys.argv[1]
    slug = sys.argv[2] if len(sys.argv) > 2 else None
    if slug is None:
        m = re.search(r"(?:v=|youtu\.be/|shorts/)([\w-]{6,})", url)
        slug = m.group(1) if m else "video"
    dest = OUT / slug
    dest.mkdir(parents=True, exist_ok=True)

    cmd = [
        str(YTDLP),
        "--ignore-errors",  # 자막 429 등 부분 실패가 영상 저장을 막지 않게
        "-f", "bv*[ext=mp4][height<=1080]+ba[ext=m4a]/b[ext=mp4]/b",
        "--merge-output-format", "mp4",
        "--write-info-json",
        "--write-subs", "--write-auto-subs", "--sub-langs", "ko,en",
        "-o", str(dest / "%(title).80s.%(ext)s"),
        url,
    ]
    code = subprocess.run(cmd).returncode
    if code == 0:
        print(f"\n저장 완료 → {dest}/")
        for f in sorted(dest.iterdir()):
            print(f"   {f.name} ({f.stat().st_size // 1024:,}KB)")
    return code


if __name__ == "__main__":
    sys.exit(main())
