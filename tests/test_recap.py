"""리캡 트랙 검증 — 라이선스 게이트, 냐옹체 린터, 클립 싱크 조립."""

import shutil
import subprocess

import pytest

from core import assemble, source_ingest
from core.breakdown import Shot
from core.schemas import Track, load_bible
from tracks.recap.nyaong_writer import write_recap
from tracks.recap.style_lint import (
    apply_guideline_substitutions,
    ending_distribution,
    lint_nyaong,
)

needs_tools = pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("espeak-ng") is None,
    reason="ffmpeg/espeak-ng 필요",
)

DEMO_LICENSE = {"source": "self", "license": "demo", "permission_ref": "t-1"}
EVENTS = [
    "남자가 섬에 도착했습니다",
    "밤에 불빛이 꺼졌습니다",
    "벽에서 금 27개를 발견했습니다",
    "배가 오지 않았습니다",
]
SHOTS = [Shot(1, 0.0, 4.0), Shot(2, 4.0, 8.0), Shot(3, 8.0, 12.0)]


# ---------------------------------------------------------------------------
# 라이선스 게이트 (규칙 5-5)
# ---------------------------------------------------------------------------

def test_source_without_license_rejected(tmp_path):
    with pytest.raises(source_ingest.SourceLicenseError, match="거부"):
        source_ingest.ingest_source(str(tmp_path / "x.mp4"), "무허가", None, tmp_path)


def test_source_missing_permission_ref_rejected(tmp_path):
    # permission_ref(허가 근거) 없이는 통과 불가 — '아마 괜찮음'을 차단
    with pytest.raises(source_ingest.SourceLicenseError, match="누락"):
        source_ingest.ingest_source(
            str(tmp_path / "x.mp4"), "근거없음",
            {"source": "s", "license": "l"}, tmp_path,
        )


# ---------------------------------------------------------------------------
# 냐옹체 린터
# ---------------------------------------------------------------------------

def test_guideline_substitutions():
    out = apply_guideline_substitutions("범인은 그를 살해했다가 시체를 숨겼다")
    assert "살해" not in out and "시체" not in out
    assert "제거했다" in out and "쓰러진 사람" in out


def test_mock_writer_passes_lint():
    bible = load_bible(Track.RECAP)
    scenes = write_recap(EVENTS, SHOTS, bible, title="테스트")
    assert lint_nyaong(scenes) == []
    dist = ending_distribution(scenes)
    assert dist["는데"] >= 0.25  # 냐옹체 핵심 스펙


def test_lint_catches_audience_reference():
    bible = load_bible(Track.RECAP)
    scenes = write_recap(EVENTS, SHOTS, bible)
    scenes[0].narration = "관객들이 놀랐는데 그가 움직였죠"
    assert any("관객" in i for i in lint_nyaong(scenes))


def test_lint_catches_three_consecutive():
    bible = load_bible(Track.RECAP)
    scenes = write_recap(EVENTS, SHOTS, bible)
    scenes[0].narration = "문을 열었는데\n비가 왔는데\n바람이 불었는데"
    assert any("3연속" in i for i in lint_nyaong(scenes))


# ---------------------------------------------------------------------------
# 클립 싱크 조립
# ---------------------------------------------------------------------------

def test_parse_clip_ref():
    assert assemble.parse_clip_ref("12.40-18.20") == (12.4, 18.2)
    with pytest.raises(assemble.AssembleError):
        assemble.parse_clip_ref("18-12")


@needs_tools
def test_preset_recap_and_shorts(tmp_path):
    # 자체 생성 6초 원본 (2샷)
    src = tmp_path / "src.mp4"
    subprocess.run([
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "color=c=0xC03030:s=640x360:d=3",
        "-f", "lavfi", "-i", "color=c=0x3080C0:s=640x360:d=3",
        "-filter_complex", "[0:v][1:v]concat=n=2:v=1[v]",
        "-map", "[v]", "-c:v", "libx264", "-preset", "veryfast",
        "-pix_fmt", "yuv420p", str(src),
    ], check=True, capture_output=True)

    meta = source_ingest.ingest_source(str(src), "t", DEMO_LICENSE, tmp_path)
    assert meta.duration > 5.5

    bible = load_bible(Track.RECAP)
    scenes = write_recap(EVENTS[:2], meta.shots or SHOTS[:2], bible)
    from core.schemas import FactSheet
    from core.tts import synthesize_episode

    sheet = FactSheet()
    audios = synthesize_episode(scenes, bible, sheet, tmp_path / "a")
    result = assemble.preset_recap(
        scenes, bible, sheet, meta.path, tmp_path / "w", tmp_path / "out.mp4",
        audio_paths={a.scene_id: a.path for a in audios},
    )
    total = sum(s.duration for s in scenes)
    assert abs(result.duration - total) < 1.0

    shorts = assemble.preset_shorts(tmp_path / "w", [1], tmp_path / "s.mp4")
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height", "-of", "csv=p=0", shorts],
        capture_output=True, text=True,
    ).stdout.strip()
    assert probe == "1080,1920"
