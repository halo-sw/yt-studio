"""assemble.py 검증 — 프리셋 2종 + 씬 교체(부분 재생성) 절대 규칙 준수."""

import shutil
import subprocess

import pytest

from core import assemble
from core.schemas import Conte, Emotion, FactSheet, Scene, SceneVisual, Track, load_bible
from core.tts import probe_duration, synthesize_episode, synthesize_scene
from tracks.playlist.library import LicenseError, Song, to_assemble_inputs

needs_tools = pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("espeak-ng") is None,
    reason="ffmpeg/espeak-ng 필요",
)


def _tone(path, freq=440.0, seconds=3):
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi", "-i", f"sine=frequency={freq}:duration={seconds}",
        "-c:a", "aac", str(path),
    ], check=True, capture_output=True)


def _scenes():
    mk = lambda i, ch, narr: Scene(
        scene_id=i, track=Track.JAPAN, chapter=ch, narration=narr,
        caption=f"자막 {i}",
        visual=SceneVisual(type="slide", ref="x", effect="kenburns" if i % 2 else "none"),
        conte=Conte(info_point=ch, emotion=Emotion(tone="차분", delivery="보통"),
                    composition="와이드", visual_direction="슬라이드"),
    )
    return [mk(1, "훅", "첫 장면입니다."), mk(2, "본론", "두 번째 장면입니다."),
            mk(3, "마무리", "마지막 장면입니다.")]


# ---------------------------------------------------------------------------
# 라이선스 (규칙 5-5)
# ---------------------------------------------------------------------------

def test_song_without_license_rejected(tmp_path):
    song = Song(path=str(tmp_path / "x.m4a"), title="무허가", license_meta=None)
    with pytest.raises(LicenseError, match="거부"):
        to_assemble_inputs([song])


# ---------------------------------------------------------------------------
# playlist_1h (M1 프롬프트 2)
# ---------------------------------------------------------------------------

@needs_tools
def test_playlist_preset_crossfade_and_timestamps(tmp_path):
    songs = []
    for i, f in enumerate([220, 330, 440]):
        p = tmp_path / f"s{i}.m4a"
        _tone(p, f, seconds=4)
        songs.append(Song(path=str(p), title=f"곡{i + 1}",
                          license_meta={"source": "self", "license": "demo"}))
    visual = assemble.make_placeholder_image("데모", tmp_path / "v.png")
    result = assemble.preset_playlist_1h(
        to_assemble_inputs(songs), visual, tmp_path / "out.mp4", tmp_path / "w",
        crossfade_sec=1.0,
    )
    # 4s×3곡 − 크로스페이드 1s×2 ≈ 10s (인코딩 패딩으로 곡당 ±0.2s 오차 허용)
    assert abs(result.duration - 10.0) < 1.0
    assert abs(probe_duration(result.out_path) - 10.0) < 1.5
    assert result.timestamps.splitlines()[0].startswith("00:00 곡1")
    # 시작점은 실측 길이 기반: 0 / d1−xf / d1+d2−2xf 근사
    assert result.track_starts[0] == 0.0
    assert abs(result.track_starts[1] - 3.0) < 0.5
    assert abs(result.track_starts[2] - 6.0) < 0.8


# ---------------------------------------------------------------------------
# longform_16x9 + replace_scene (M1 프롬프트 3, 규칙 5-1·5-2)
# ---------------------------------------------------------------------------

@needs_tools
def test_longform_render_and_scene_replace(tmp_path):
    bible = load_bible(Track.JAPAN)
    sheet = FactSheet(facts={})
    scenes = _scenes()
    audios = synthesize_episode(scenes, bible, sheet, tmp_path / "a")
    audio_paths = {a.scene_id: a.path for a in audios}
    bgm = tmp_path / "bgm.m4a"
    _tone(bgm, 174, seconds=2)

    result = assemble.preset_longform_16x9(
        scenes, bible, sheet, tmp_path / "w", tmp_path / "ep.mp4",
        audio_paths=audio_paths, bgm_path=bgm,
    )
    total = sum(s.duration for s in scenes)
    assert abs(result.duration - total) < 1.0
    # 챕터 마커 3개 (미드롤 근거 데이터)
    assert result.chapters_text.count("\n") == 2
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_chapters", "-of", "csv", "ep.mp4"],
        cwd=tmp_path, capture_output=True, text=True,
    ).stdout
    assert probe.count("chapter") == 3

    # --- 씬 2 교체 (규칙 5-2: 다른 세그먼트 재렌더 금지) ---
    seg1_mtime = (tmp_path / "w" / "seg_001.mp4").stat().st_mtime
    new_scene = scenes[1].model_copy(deep=True)
    new_scene.narration = "두 번째 장면을 완전히 새로 씁니다. 조금 더 길게 말합니다."
    new_scene.duration = None
    new_audio = synthesize_scene(new_scene, bible, sheet, tmp_path / "a2")
    replaced = assemble.replace_scene(
        scenes, new_scene, bible, sheet, tmp_path / "w", tmp_path / "ep2.mp4",
        new_audio_path=new_audio.path, bgm_path=bgm,
    )
    assert (tmp_path / "ep2.mp4").exists()
    # 교체 씬이 더 길어졌으니 전체도 길어짐 (경계 크로스페이드 2×80ms 감안)
    new_total = scenes[0].duration + new_scene.duration + scenes[2].duration
    assert abs(replaced.duration - (new_total - 2 * assemble.SCENE_XFADE_SEC)) < 1.0
    # 규칙 5-2: seg_001은 건드리지 않았다
    assert (tmp_path / "w" / "seg_001.mp4").stat().st_mtime == seg1_mtime


@needs_tools
def test_replace_scene_requires_existing_segments(tmp_path):
    bible = load_bible(Track.JAPAN)
    scenes = _scenes()
    scenes[0].duration = 1.0
    with pytest.raises(assemble.AssembleError, match="세그먼트 없음"):
        assemble.replace_scene(
            scenes, scenes[0], bible, FactSheet(), tmp_path / "none",
            tmp_path / "o.mp4", new_audio_path=tmp_path / "x.wav",
        )
