"""Higgsfield 씬 비주얼 생성 — 하이브리드 기본 전략 (CLAUDE.md 10장 갱신 반영).

비용 정책 (10분 1편 기준 ~80크레딧):
  - 이미지: 전 씬 GPT Image 2 1k (4크레딧/장) — 실사 스타일 프리셋
  - 모션:   핵심 씬만 Minimax Hailuo i2v 6초 (6크레딧/클립)
            핵심 씬 = 훅 + 미드롤 직전 클리프행어 + 절정 + 엔딩 (규칙 5-7의
            이탈 결정 지점) — 나머지 씬은 assemble의 Ken Burns(무료)
  - 사용한 크레딧은 관제(규칙 5-8)에 집계할 것

공식 CLI(higgsfield) 경유만 허용 — 비공식 API 호출 금지.
"""

from __future__ import annotations

import subprocess
import urllib.request
from pathlib import Path

HF_BIN = str(Path.home() / ".local/bin/higgsfield")

# 실사 스타일 프리셋 — "인위적인 느낌" 배제: 필름 스틸 문법으로 고정
PHOTOREAL_STYLE = (
    "Cinematic photorealistic film still from a Korean drama, shot on 35mm, "
    "natural available light, shallow depth of field, muted realistic color "
    "grade, subtle film grain, documentary realism, imperfect framing like a "
    "real photograph. Not illustration, not 3D render, no stylization. "
    "No text, no letters, no watermark. "
)

IMAGE_MODEL = "gpt_image_2"
IMAGE_RESOLUTION = "1k"          # 4크레딧 — 최종 1080p 렌더에 충분
MOTION_MODEL = "minimax_hailuo"  # 6크레딧/6초 — i2v 최저가 대비 품질 우수
MOTION_BASE = (
    "Subtle cinematic live-action motion, single continuous shot, no cuts, "
    "keep photorealistic look and original composition, no text. "
)


def _run_hf(args: list[str]) -> str | None:
    """higgsfield CLI 실행 → 결과 URL (실패 시 None).

    --wait-timeout과 별개로 프로세스 자체가 무응답으로 매달리는 사례가 있어
    (2026-07-24 시장 연작 생성 중 2시간 행) 하드 타임아웃을 건다.
    """
    try:
        proc = subprocess.run([HF_BIN, *args], capture_output=True, text=True,
                              timeout=1800)
    except subprocess.TimeoutExpired:
        print("   [hf] 실패 — 프로세스 타임아웃(30분), 다음 재시도 패스에서 재실행",
              flush=True)
        return None
    urls = [ln.strip() for ln in proc.stdout.splitlines()
            if ln.strip().startswith("https://")]
    if proc.returncode != 0 or not urls:
        print(f"   [hf] 실패 — {(proc.stderr or proc.stdout)[-200:]}", flush=True)
        return None
    return urls[-1]


def pick_motion_scenes(n_scenes: int, midroll_scene_ids: list[int] | None = None) -> set[int]:
    """하이브리드 핵심 씬 선정: 훅 2 + 미드롤 직전 + 절정(75~85% 지점) + 엔딩."""
    key = {1, 2, n_scenes}                              # 훅 + 엔딩
    key.add(max(1, round(n_scenes * 0.8)))              # 절정 부근
    key.add(max(1, round(n_scenes * 0.5)))              # 중반 리텐션 포인트
    for sid in midroll_scene_ids or []:                 # 미드롤 직전 클리프행어
        key.add(min(max(sid, 1), n_scenes))
    return key


def gen_image(desc: str, out_png: Path, style: str = PHOTOREAL_STYLE) -> bool:
    """씬 묘사 → 실사 스틸 1장. 이미 있으면 건너뜀."""
    if out_png.exists():
        return True
    out_png.parent.mkdir(parents=True, exist_ok=True)
    url = _run_hf(["generate", "create", IMAGE_MODEL,
                   "--prompt", style + desc,
                   "--aspect_ratio", "16:9", "--resolution", IMAGE_RESOLUTION,
                   "--wait", "--wait-timeout", "15m"])
    if url:
        urllib.request.urlretrieve(url, out_png)
    return url is not None


def gen_motion(img_png: Path, motion_desc: str, out_mp4: Path) -> bool:
    """씬 스틸 → 6초 모션 클립 (i2v). 이미 있으면 건너뜀."""
    if out_mp4.exists():
        return True
    if not img_png.exists():
        print(f"   [hf] 원본 스틸 없음: {img_png}", flush=True)
        return False
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    # resolution은 CLI가 숫자로 강제 변환해 타입 오류가 나므로 서버 기본값(768) 사용
    url = _run_hf(["generate", "create", MOTION_MODEL,
                   "--prompt", MOTION_BASE + motion_desc,
                   "--start-image", str(img_png),
                   "--duration", "6",
                   "--wait", "--wait-timeout", "20m"])
    if url:
        urllib.request.urlretrieve(url, out_mp4)
    return url is not None
