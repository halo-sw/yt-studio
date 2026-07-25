"""사연 편지함 1호 — 최종 조립 (프레임 7조각 + 6편 + 브랜드 범퍼 concat).

sijang_assemble과 동일한 무손실 concat 방식 (전 세그먼트 동일 파이프라인 규격).
실행: .venv/bin/python -m tracks.natepan.pyeonji_assemble
"""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
P = ROOT / "data/assets/produce"
FRAME = P / "pyeonji_frame/work"
BRAND = P / "pyeonji_series/brand"      # 편지함 무드 신규 범퍼 (2026-07-25 교체)
OUT = P / "pyeonji_series"

ORDER: list[tuple[Path, str | None]] = [
    (FRAME / "seg_001.mp4", "여섯 통의 편지 — 오프닝"),
    (BRAND / "intro_bumper.mp4", None),
    (P / "pyeonji_gongjang/episode.mp4", "첫 번째 편지 — 삼십 년 일한 값, 환갑날 받은 봉투"),
    (FRAME / "seg_002.mp4", "두 번째 편지 — 혼수 목록에 그어진 빨간 줄"),
    (P / "pyeonji_yaksa/episode.mp4", None),
    (FRAME / "seg_003.mp4", "세 번째 편지 — 보호자 칸에 이름을 적은 사위"),
    (P / "pyeonji_sawi/episode.mp4", None),
    (FRAME / "seg_004.mp4", "네 번째 편지 — 열여덟 번 건너뛴 명절, 장인의 팔순"),
    (P / "pyeonji_palsun/episode.mp4", None),
    (FRAME / "seg_005.mp4", "다섯 번째 편지 — 새벽 골목의 빗자루 소리"),
    (P / "pyeonji_ganhosa/episode.mp4", None),
    (FRAME / "seg_006.mp4", "여섯 번째 편지 — 유언장에서 지워진 이름"),
    (P / "pyeonji_sangsok/episode.mp4", None),
    (FRAME / "seg_007.mp4", "편지함을 닫으며"),
    (BRAND / "outro_bumper.mp4", None),
]


def probe(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True, check=True).stdout.strip()
    return float(out)


def main() -> None:
    missing = [str(f) for f, _ in ORDER if not f.exists()]
    if missing:
        raise SystemExit("누락 세그먼트:\n  " + "\n  ".join(missing))

    OUT.mkdir(parents=True, exist_ok=True)
    concat = OUT / "concat.txt"
    concat.write_text("".join(f"file '{f}'\n" for f, _ in ORDER))

    final = OUT / "series.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0",
                    "-i", str(concat), "-c", "copy", str(final)], check=True)

    t, lines = 0.0, []
    for f, title in ORDER:
        if title:
            mm, ss = divmod(int(t), 60)
            hh, mm = divmod(mm, 60)
            stamp = f"{hh}:{mm:02d}:{ss:02d}" if hh else f"{mm:02d}:{ss:02d}"
            lines.append(f"{stamp} {title}")
        t += probe(f)
    (OUT / "chapters.txt").write_text("\n".join(lines) + "\n")

    mm, ss = divmod(int(t), 60)
    print(f"→ {final} ({mm}분 {ss}초)")
    print((OUT / "chapters.txt").read_text())


if __name__ == "__main__":
    main()
