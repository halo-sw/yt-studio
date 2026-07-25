"""시장 골목 연작 — 최종 조립 (프레임 조각 + 7편 concat).

전 세그먼트가 동일 파이프라인 산출물(h264 1080p30 + aac 44.1k mono)이라
concat demuxer -c copy로 무손실 이어붙인다. BGM은 원본 에피소드들과
동일하게 없음(추가 시 규칙 5-1의 글로벌 트랙 방식으로 별도 믹스).

실행: .venv/bin/python -m tracks.natepan.sijang_assemble
"""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
P = ROOT / "data/assets/produce"
FRAME = P / "sijang_frame/work"
OUT = P / "sijang_series"

# (파일, 챕터 제목 | None=직전 챕터에 흡수)
BRAND = P / "sijang_series/brand"

ORDER: list[tuple[Path, str | None]] = [
    (FRAME / "seg_001.mp4", "오프닝 — 어느 오래된 시장"),
    (BRAND / "intro_bumper.mp4", None),      # 채널 브랜드 범퍼 5초 (톡톡드라마썰)
    (P / "sijang_gukbap/episode.mp4", "국밥 두 그릇"),
    (FRAME / "seg_002.mp4", "첫 월요일의 구두"),
    (P / "sijang_gudubang/episode.mp4", None),
    (FRAME / "seg_003.mp4", "쌀가게의 장부"),
    (P / "sijang_jangbu/episode.mp4", None),
    (FRAME / "seg_004.mp4", "등판이 닳는 점퍼"),
    (P / "sijang_suseon/episode.mp4", None),
    (FRAME / "seg_005.mp4", "시장 양 끝의 두 떡집"),
    (P / "sijang_tteokjip/episode.mp4", None),
    (FRAME / "seg_006.mp4", "입은 흔적 없는 교복"),
    (P / "sijang_laundry/episode.mp4", None),
    (FRAME / "seg_007.mp4", "사십 년 만의 외상값"),
    (P / "sijang_munbanggu/episode.mp4", None),
    (FRAME / "seg_008.mp4", "골목의 저녁 — 마무리"),
    (BRAND / "outro_bumper.mp4", None),      # 구독·좋아요 아웃트로 8초
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

    # 챕터 타임스탬프 (설명란용)
    t, lines = 0.0, []
    for f, title in ORDER:
        if title:
            mm, ss = divmod(int(t), 60)
            hh, mm = divmod(mm, 60)
            stamp = f"{hh}:{mm:02d}:{ss:02d}" if hh else f"{mm:02d}:{ss:02d}"
            lines.append(f"{stamp} {title}")
        t += probe(f)
    chapters = OUT / "chapters.txt"
    chapters.write_text("\n".join(lines) + "\n")

    mm, ss = divmod(int(t), 60)
    print(f"→ {final} ({mm}분 {ss}초)")
    print(chapters.read_text())


if __name__ == "__main__":
    main()
