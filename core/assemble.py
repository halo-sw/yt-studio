"""core/assemble.py — FFmpeg 조립: 프리셋 + 오디오 2트랙 믹스 + 씬 교체.

프리셋:
- preset_playlist_1h : loudnorm → 곡간 크로스페이드 → 루프 비주얼 → 타임스탬프
- preset_longform_16x9: 씬 이미지 + Ken Burns + 자막 번인 + 2트랙 오디오 믹스
                        + 미드롤 챕터 마커

절대 규칙 반영:
- 규칙 5-1 오디오 2트랙: 내레이션·효과음=씬 레이어(-14 LUFS)로 씬 세그먼트에
  굽고, BGM=에피소드 글로벌 트랙(-26 LUFS 언더베드)은 최종 믹스 단계에서만
  합성한다. 씬 교체 시 BGM은 건드리지 않는다 — replace_scene은 세그먼트만
  다시 만들고 같은 BGM으로 최종 믹스를 다시 할 뿐이다.
- 규칙 5-2 부분 재생성: replace_scene은 교체 씬 세그먼트 하나만 재렌더하고,
  교체 경계 두 곳에만 50~100ms(기본 80ms) 크로스페이드를 넣어 이어붙인다.
  다른 씬 세그먼트 파일은 절대 다시 만들지 않는다 (전체 재렌더 금지).
- 규칙 5-3: 자막 번인 직전에 {{fact:key}}를 fact_sheet로 치환한다.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from core.schemas import Bible, FactSheet, Scene, VisualEffect
from core.tts import probe_duration, resolve_fact_tokens

# 규칙 5-1 — 트랙별 라우드니스 목표
NARRATION_LUFS = -14.0   # 씬 레이어 (내레이션·효과음)
BGM_LUFS = -26.0         # 에피소드 글로벌 언더베드
MUSIC_LUFS = -14.0       # 플레이리스트 본편 곡 (곡 자체가 콘텐츠)

# 규칙 5-2 — 씬 교체 경계 크로스페이드 (50~100ms 범위 안)
SCENE_XFADE_SEC = 0.08

VIDEO_SIZE = (1920, 1080)
FPS = 30

# 자막 번인용 한글 폰트 탐색 순서 — CF_FONT_PATH 환경변수가 최우선 (로컬 실행 대응)
_KOREAN_FONTS = (
    # Linux (fonts-noto-cjk)
    "/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    # macOS
    "/System/Library/Fonts/AppleSDGothicNeo.ttc",
    "/Library/Fonts/AppleSDGothicNeo.ttc",
    # Windows (맑은 고딕)
    "C:/Windows/Fonts/malgun.ttf",
    "C:/Windows/Fonts/malgunbd.ttf",
)


class AssembleError(RuntimeError):
    pass


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise AssembleError(f"ffmpeg 실패: {' '.join(cmd[:4])}…\n{proc.stderr[-1200:]}")
    return proc


def _font_file(bible: Bible | None = None) -> str:
    import os

    override = os.getenv("CF_FONT_PATH")
    if override:
        if Path(override).exists():
            return override
        raise AssembleError(f"CF_FONT_PATH 경로에 폰트 없음: {override}")
    for p in _KOREAN_FONTS:
        if Path(p).exists():
            return p
    raise AssembleError(
        "한글 폰트를 찾지 못함 — Linux: fonts-noto-cjk 설치 / "
        "기타 OS: .env에 CF_FONT_PATH=폰트파일경로 지정"
    )


def _fmt_ts(seconds: float) -> str:
    s = int(seconds)
    if s >= 3600:
        return f"{s // 3600}:{(s % 3600) // 60:02d}:{s % 60:02d}"
    return f"{s // 60:02d}:{s % 60:02d}"


# ---------------------------------------------------------------------------
# 플레이스홀더 비주얼 (M1: 비주얼은 플레이스홀더 허용 — MJ/Higgsfield는 수동 대기열)
# ---------------------------------------------------------------------------

def make_placeholder_image(
    title: str, out_path: str | Path, subtitle: str = "",
    size: tuple[int, int] = VIDEO_SIZE, palette: int = 0,
) -> Path:
    """씬 비주얼이 아직 없을 때 쓰는 자리표시 슬라이드 (PIL 그라데이션+텍스트)."""
    from PIL import Image, ImageDraw, ImageFont

    palettes = [
        ((24, 26, 38), (64, 46, 92)),     # 딥 퍼플
        ((16, 32, 44), (30, 74, 84)),     # 딥 틸
        ((38, 24, 24), (92, 52, 40)),     # 웜 브라운
    ]
    top, bottom = palettes[palette % len(palettes)]
    w, h = size
    img = Image.new("RGB", size)
    for y in range(h):
        t = y / h
        img.paste(
            tuple(round(top[i] + (bottom[i] - top[i]) * t) for i in range(3)),
            (0, y, w, y + 1),
        )
    draw = ImageDraw.Draw(img)
    font_big = ImageFont.truetype(_font_file(), 72)
    font_small = ImageFont.truetype(_font_file(), 40)
    draw.text((w // 2, h // 2 - 60), title, font=font_big, anchor="mm", fill=(240, 238, 232))
    if subtitle:
        draw.text((w // 2, h // 2 + 60), subtitle, font=font_small, anchor="mm", fill=(200, 198, 190))
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path)
    return out_path


# ---------------------------------------------------------------------------
# preset_playlist_1h — loudnorm → 크로스페이드 → 루프 비주얼 → 타임스탬프
# ---------------------------------------------------------------------------

@dataclass
class PlaylistTrackIn:
    """조립 입력 곡. 규칙 5-5: license_meta 없는 곡은 library.ingest가 이미
    거부했으므로 여기 도달한 곡은 라이선스 확인 완료로 간주한다."""

    path: str
    title: str
    artist: str = ""


@dataclass
class PlaylistResult:
    out_path: str
    duration: float
    timestamps: str          # 유튜브 설명란용 "MM:SS 제목 — 아티스트"
    track_starts: list[float] = field(default_factory=list)


def preset_playlist_1h(
    tracks: list[PlaylistTrackIn],
    visual_path: str | Path,
    out_path: str | Path,
    workdir: str | Path,
    crossfade_sec: float = 2.0,
) -> PlaylistResult:
    """플레이리스트 프리셋: loudnorm → 곡간 크로스페이드 → 루프 비주얼 → 타임스탬프.

    60분이든 3분(M1 검증 미니)이든 곡 목록 길이에 따라 동일하게 동작한다.
    """
    if not tracks:
        raise AssembleError("곡 목록이 비어 있음")
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # 1) 곡별 loudnorm (본편 곡이므로 MUSIC_LUFS)
    normed: list[Path] = []
    durations: list[float] = []
    for i, t in enumerate(tracks):
        norm = workdir / f"norm_{i:03d}.m4a"
        _run([
            "ffmpeg", "-y", "-i", t.path,
            "-af", f"loudnorm=I={MUSIC_LUFS}:TP=-1.5:LRA=11",
            "-ar", "44100", "-c:a", "aac", "-b:a", "192k", str(norm),
        ])
        normed.append(norm)
        durations.append(probe_duration(norm))

    # 2) 곡간 크로스페이드 체인 + 타임스탬프 (시작점 = 누적 길이 - 누적 오버랩)
    track_starts: list[float] = []
    cursor = 0.0
    for i, d in enumerate(durations):
        track_starts.append(round(cursor, 2))
        cursor += d - (crossfade_sec if i < len(durations) - 1 else 0.0)
    total = cursor

    mixed = workdir / "mix.m4a"
    if len(normed) == 1:
        mixed = normed[0]
    else:
        inputs: list[str] = []
        for p in normed:
            inputs += ["-i", str(p)]
        graph = []
        prev = "[0:a]"
        for i in range(1, len(normed)):
            out = f"[x{i}]" if i < len(normed) - 1 else "[aout]"
            graph.append(
                f"{prev}[{i}:a]acrossfade=d={crossfade_sec}:c1=tri:c2=tri{out}"
            )
            prev = out
        _run([
            "ffmpeg", "-y", *inputs, "-filter_complex", ";".join(graph),
            "-map", "[aout]", "-c:a", "aac", "-b:a", "192k", str(mixed),
        ])

    # 3) 루프 비주얼 (이미지 → 무한 루프, 영상 → stream_loop) + 최종 먹싱
    visual = Path(visual_path)
    is_image = visual.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}
    vin = ["-loop", "1", "-i", str(visual)] if is_image else ["-stream_loop", "-1", "-i", str(visual)]
    _run([
        "ffmpeg", "-y", *vin, "-i", str(mixed),
        "-map", "0:v", "-map", "1:a", "-shortest",
        "-vf", f"scale={VIDEO_SIZE[0]}:{VIDEO_SIZE[1]},format=yuv420p",
        "-r", str(FPS), "-c:v", "libx264", "-preset", "veryfast", "-tune", "stillimage",
        "-c:a", "copy", str(out_path),
    ])

    timestamps = "\n".join(
        f"{_fmt_ts(start)} {t.title}" + (f" — {t.artist}" if t.artist else "")
        for start, t in zip(track_starts, tracks)
    )
    return PlaylistResult(
        out_path=str(out_path), duration=round(total, 2),
        timestamps=timestamps, track_starts=track_starts,
    )


# ---------------------------------------------------------------------------
# preset_longform_16x9 — 씬 세그먼트 렌더 → 결합 → BGM 언더베드 → 챕터 마커
# ---------------------------------------------------------------------------

@dataclass
class EpisodeRender:
    out_path: str
    duration: float
    chapters_text: str       # 유튜브 설명란용 챕터 타임스탬프
    segment_paths: list[str] = field(default_factory=list)


def render_scene_segment(
    scene: Scene,
    audio_path: str | Path,
    seg_path: str | Path,
    bible: Bible,
    fact_sheet: FactSheet,
    visual_path: str | Path | None = None,
) -> Path:
    """씬 하나 → 세그먼트 mp4. 부분 재생성(규칙 5-2)의 렌더 단위.

    - 오디오: 씬 레이어만 loudnorm -14 LUFS로 굽는다. BGM 없음 (규칙 5-1).
    - 비주얼: 지정 없으면 플레이스홀더 슬라이드 자동 생성 (M1 허용).
    - Ken Burns: visual.effect가 kenburns면 zoompan으로 느린 줌인.
    - 자막: caption을 fact 치환 후 하단 번인 (바이블 subtitle_tokens 폰트 크기).
    """
    seg_path = Path(seg_path)
    seg_path.parent.mkdir(parents=True, exist_ok=True)
    duration = scene.duration or probe_duration(audio_path)

    if visual_path is None:
        visual_path = make_placeholder_image(
            scene.chapter, seg_path.with_suffix(".png"),
            subtitle=scene.conte.visual_direction[:40],
            palette=scene.scene_id,
        )

    caption = resolve_fact_tokens(scene.caption, fact_sheet).replace("'", "’").replace(":", "\\:")
    font = _font_file(bible)
    fontsize = int(bible.subtitle_tokens.get("size", "48"))
    fontcolor = bible.subtitle_tokens.get("color", "#FFFFFF")

    frames = max(int(duration * FPS), 1)
    w, h = VIDEO_SIZE
    if scene.visual.effect is VisualEffect.KENBURNS:
        # 느린 줌인 1.0→1.08 — 업스케일 후 zoompan으로 서브픽셀 떨림 완화
        vf = (
            f"scale={w * 2}:{h * 2},"
            f"zoompan=z='1+0.08*on/{frames}':d={frames}:s={w}x{h}:fps={FPS}"
        )
    else:
        vf = f"scale={w}:{h},fps={FPS}"
    if caption:
        vf += (
            f",drawtext=fontfile={font}:text='{caption}':"
            f"fontsize={fontsize}:fontcolor={fontcolor}:"
            f"x=(w-text_w)/2:y=h-{fontsize * 3}:"
            f"box=1:boxcolor=black@0.45:boxborderw=18"
        )
    vf += ",format=yuv420p"

    _run([
        "ffmpeg", "-y", "-loop", "1", "-i", str(visual_path), "-i", str(audio_path),
        "-t", f"{duration:.3f}",
        "-vf", vf,
        "-af", f"loudnorm=I={NARRATION_LUFS}:TP=-1.5:LRA=11,aresample=44100",
        "-c:v", "libx264", "-preset", "veryfast",
        "-c:a", "aac", "-b:a", "160k", "-ar", "44100",
        str(seg_path),
    ])
    return seg_path


def _concat_plain(segments: list[Path], out: Path, workdir: Path) -> None:
    """세그먼트 단순 결합 (재인코딩 없음 — 초기 전체 렌더 경로)."""
    lst = workdir / "concat.txt"
    lst.write_text("".join(f"file '{p.resolve()}'\n" for p in segments), encoding="utf-8")
    _run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(lst),
        "-c", "copy", str(out),
    ])


def _concat_with_boundary_xfade(
    parts: list[Path], out: Path, xfade: float = SCENE_XFADE_SEC
) -> None:
    """parts 사이 경계에만 비디오+오디오 크로스페이드를 넣어 결합 (규칙 5-2).

    replace_scene 전용 — [앞 묶음][교체 씬][뒷 묶음] 3파트, 경계는 최대 2곳.
    """
    inputs: list[str] = []
    for p in parts:
        inputs += ["-i", str(p)]
    durs = [probe_duration(p) for p in parts]
    graph: list[str] = []
    prev_v, prev_a = "[0:v]", "[0:a]"
    offset = 0.0
    for i in range(1, len(parts)):
        offset += durs[i - 1] - xfade
        v_out = f"[v{i}]" if i < len(parts) - 1 else "[vout]"
        a_out = f"[a{i}]" if i < len(parts) - 1 else "[aout]"
        graph.append(
            f"{prev_v}[{i}:v]xfade=transition=fade:duration={xfade}:offset={offset:.3f}{v_out}"
        )
        graph.append(f"{prev_a}[{i}:a]acrossfade=d={xfade}:c1=tri:c2=tri{a_out}")
        prev_v, prev_a = v_out, a_out
    _run([
        "ffmpeg", "-y", *inputs, "-filter_complex", ";".join(graph),
        "-map", prev_v, "-map", prev_a,
        "-c:v", "libx264", "-preset", "veryfast",
        "-c:a", "aac", "-b:a", "160k", str(out),
    ])


def _chapters_from_scenes(scenes: list[Scene]) -> list[tuple[str, float]]:
    """씬 목록 → (챕터명, 시작초). 같은 챕터의 첫 씬이 챕터 시작 (미드롤 마커)."""
    chapters: list[tuple[str, float]] = []
    cursor = 0.0
    seen_last = None
    for s in sorted(scenes, key=lambda s: s.scene_id):
        if s.chapter != seen_last:
            chapters.append((s.chapter, round(cursor, 2)))
            seen_last = s.chapter
        cursor += s.duration or 0.0
    return chapters


def _embed_chapters_and_bgm(
    master: Path,
    out_path: Path,
    chapters: list[tuple[str, float]],
    total: float,
    workdir: Path,
    bgm_path: str | Path | None,
) -> None:
    """최종 믹스: BGM 언더베드(-26 LUFS, 규칙 5-1) 합성 + 챕터 메타데이터 삽입.

    BGM은 여기서만 합성된다 — 씬 세그먼트에는 절대 굽지 않는다.
    """
    meta = workdir / "chapters.ffmeta"
    lines = [";FFMETADATA1"]
    for i, (name, start) in enumerate(chapters):
        end = chapters[i + 1][1] if i + 1 < len(chapters) else total
        lines += [
            "[CHAPTER]", "TIMEBASE=1/1000",
            f"START={int(start * 1000)}", f"END={int(end * 1000)}",
            f"title={name}",
        ]
    meta.write_text("\n".join(lines) + "\n", encoding="utf-8")

    if bgm_path:
        _run([
            "ffmpeg", "-y", "-i", str(master),
            "-stream_loop", "-1", "-i", str(bgm_path),
            "-i", str(meta), "-map_metadata", "2",
            "-filter_complex",
            (
                f"[1:a]loudnorm=I={BGM_LUFS}:TP=-2.0:LRA=7,aresample=44100[bgm];"
                f"[0:a][bgm]amix=inputs=2:duration=first:normalize=0[aout]"
            ),
            "-map", "0:v", "-map", "[aout]",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "160k",
            "-t", f"{total:.3f}", str(out_path),
        ])
    else:
        _run([
            "ffmpeg", "-y", "-i", str(master), "-i", str(meta),
            "-map_metadata", "1", "-map", "0", "-c", "copy", str(out_path),
        ])


def preset_longform_16x9(
    scenes: list[Scene],
    bible: Bible,
    fact_sheet: FactSheet,
    workdir: str | Path,
    out_path: str | Path,
    *,
    audio_paths: dict[int, str | Path],
    visual_paths: dict[int, str | Path] | None = None,
    bgm_path: str | Path | None = None,
) -> EpisodeRender:
    """롱폼 16:9 프리셋 — 씬 이미지+Ken Burns+자막 번인+2트랙 믹스+챕터 마커.

    audio_paths: tts.synthesize_episode 산출물 {scene_id: 오디오 경로}.
    visual_paths: 없으면 씬별 플레이스홀더 생성 (M1 허용).
    """
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    out_path = Path(out_path)
    ordered = sorted(scenes, key=lambda s: s.scene_id)
    visual_paths = visual_paths or {}

    segments: list[Path] = []
    for s in ordered:
        seg = workdir / f"seg_{s.scene_id:03d}.mp4"
        render_scene_segment(
            s, audio_paths[s.scene_id], seg, bible, fact_sheet,
            visual_path=visual_paths.get(s.scene_id),
        )
        segments.append(seg)

    master = workdir / "master.mp4"
    _concat_plain(segments, master, workdir)
    total = probe_duration(master)
    chapters = _chapters_from_scenes(ordered)
    _embed_chapters_and_bgm(master, out_path, chapters, total, workdir, bgm_path)

    chapters_text = "\n".join(f"{_fmt_ts(t)} {name}" for name, t in chapters)
    return EpisodeRender(
        out_path=str(out_path), duration=round(total, 2),
        chapters_text=chapters_text, segment_paths=[str(p) for p in segments],
    )


# ---------------------------------------------------------------------------
# preset_recap — 리캡 트랙: 라이선스 확보 원본 클립 + 냐옹체 내레이션 (plans/12)
# ---------------------------------------------------------------------------

def parse_clip_ref(ref: str) -> tuple[float, float]:
    """visual.ref '12.40-18.20' → (start, end)초. nyaong_writer가 생성한다."""
    import re as _re

    m = _re.fullmatch(r"([\d.]+)-([\d.]+)", ref.strip())
    if not m:
        raise AssembleError(f"클립 타임코드 형식 아님: {ref!r}")
    start, end = float(m.group(1)), float(m.group(2))
    if end <= start:
        raise AssembleError(f"클립 구간 역전: {ref!r}")
    return start, end


def render_clip_segment(
    scene: Scene,
    audio_path: str | Path,
    source_path: str | Path,
    seg_path: str | Path,
    bible: Bible,
    fact_sheet: FactSheet,
) -> Path:
    """리캡 씬 세그먼트: 원본 샷 구간을 내레이션 길이에 맞춰 컷.

    - 원본 오디오는 쓰지 않는다 (저작권 방어 + 규칙 5-1: 씬 오디오는
      내레이션 -14 LUFS만). 클립이 내레이션보다 짧으면 마지막 프레임 홀드.
    - source_path는 source_ingest의 라이선스 게이트(규칙 5-5)를 통과한
      원본만 온다 — 여기서 다시 검증하지 않는 대신 우회 경로를 만들지 않는다.
    """
    seg_path = Path(seg_path)
    seg_path.parent.mkdir(parents=True, exist_ok=True)
    target = scene.duration or probe_duration(audio_path)
    clip_start, clip_end = parse_clip_ref(scene.visual.ref)

    caption = resolve_fact_tokens(scene.caption, fact_sheet).replace("'", "’").replace(":", "\\:")
    font = _font_file(bible)
    fontsize = int(bible.subtitle_tokens.get("size", "54"))
    fontcolor = bible.subtitle_tokens.get("color", "#FFFFFF")
    w, h = VIDEO_SIZE

    vf = (
        f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
        f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,fps={FPS},"
        f"tpad=stop_mode=clone:stop_duration={target:.3f}"
    )
    if caption:
        vf += (
            f",drawtext=fontfile={font}:text='{caption}':"
            f"fontsize={fontsize}:fontcolor={fontcolor}:"
            f"x=(w-text_w)/2:y=h-{fontsize * 3}:"
            f"box=1:boxcolor=black@0.45:boxborderw=18"
        )
    vf += ",format=yuv420p"

    _run([
        "ffmpeg", "-y",
        "-ss", f"{clip_start:.3f}", "-t", f"{clip_end - clip_start:.3f}",
        "-i", str(source_path), "-i", str(audio_path),
        "-map", "0:v", "-map", "1:a", "-t", f"{target:.3f}",
        "-vf", vf,
        "-af", f"loudnorm=I={NARRATION_LUFS}:TP=-1.5:LRA=11,aresample=44100",
        "-c:v", "libx264", "-preset", "veryfast",
        "-c:a", "aac", "-b:a", "160k", "-ar", "44100",
        str(seg_path),
    ])
    return seg_path


def preset_recap(
    scenes: list[Scene],
    bible: Bible,
    fact_sheet: FactSheet,
    source_path: str | Path,
    workdir: str | Path,
    out_path: str | Path,
    *,
    audio_paths: dict[int, str | Path],
    bgm_path: str | Path | None = None,
) -> EpisodeRender:
    """리캡 프리셋: 원본 샷 컷 싱크 + 자막 번인 + 2트랙 믹스 + 챕터.

    세그먼트 파일 규약(seg_XXX.mp4)이 longform과 같아 씬 교체 흐름도
    동일하게 동작한다 (규칙 5-2).
    """
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    out_path = Path(out_path)
    ordered = sorted(scenes, key=lambda s: s.scene_id)

    segments: list[Path] = []
    for s in ordered:
        seg = workdir / f"seg_{s.scene_id:03d}.mp4"
        render_clip_segment(s, audio_paths[s.scene_id], source_path, seg, bible, fact_sheet)
        segments.append(seg)

    master = workdir / "master.mp4"
    _concat_plain(segments, master, workdir)
    total = probe_duration(master)
    chapters = _chapters_from_scenes(ordered)
    _embed_chapters_and_bgm(master, out_path, chapters, total, workdir, bgm_path)

    chapters_text = "\n".join(f"{_fmt_ts(t)} {name}" for name, t in chapters)
    return EpisodeRender(
        out_path=str(out_path), duration=round(total, 2),
        chapters_text=chapters_text, segment_paths=[str(p) for p in segments],
    )


SHORTS_SIZE = (1080, 1920)


def preset_shorts(
    workdir: str | Path,
    scene_ids: list[int],
    out_path: str | Path,
) -> str:
    """쇼츠 파생: 렌더된 세그먼트에서 훅 씬들을 골라 9:16 세로 재컷.

    본편 세그먼트를 재사용하므로 재렌더 비용이 크롭 인코딩뿐이다.
    """
    workdir = Path(workdir)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    segs = [workdir / f"seg_{sid:03d}.mp4" for sid in scene_ids]
    for s in segs:
        if not s.exists():
            raise AssembleError(f"세그먼트 없음: {s} — 본편 프리셋을 먼저 렌더")

    sw, sh = SHORTS_SIZE
    inputs: list[str] = []
    for s in segs:
        inputs += ["-i", str(s)]
    chains = []
    for i in range(len(segs)):
        chains.append(
            f"[{i}:v]crop=ih*{sw}/{sh}:ih:(iw-ih*{sw}/{sh})/2:0,"
            f"scale={sw}:{sh},fps={FPS},format=yuv420p[v{i}]"
        )
    concat_in = "".join(f"[v{i}][{i}:a]" for i in range(len(segs)))
    chains.append(f"{concat_in}concat=n={len(segs)}:v=1:a=1[vout][aout]")
    _run([
        "ffmpeg", "-y", *inputs, "-filter_complex", ";".join(chains),
        "-map", "[vout]", "-map", "[aout]",
        "-c:v", "libx264", "-preset", "veryfast",
        "-c:a", "aac", "-b:a", "160k", str(out_path),
    ])
    return str(out_path)


def replace_scene(
    scenes: list[Scene],
    new_scene: Scene,
    bible: Bible,
    fact_sheet: FactSheet,
    workdir: str | Path,
    out_path: str | Path,
    *,
    new_audio_path: str | Path,
    new_visual_path: str | Path | None = None,
    bgm_path: str | Path | None = None,
) -> EpisodeRender:
    """씬 교체 (규칙 5-2): 교체 씬 세그먼트 하나만 재렌더하고 경계 80ms
    크로스페이드로 이어붙인다.

    - 다른 씬의 seg_*.mp4는 재사용한다 (전체 재렌더 금지).
    - BGM은 건드리지 않는다 — 같은 bgm_path로 최종 믹스만 다시 한다 (규칙 5-1).
    """
    workdir = Path(workdir)
    out_path = Path(out_path)
    ordered = sorted(scenes, key=lambda s: s.scene_id)
    idx = next(
        (i for i, s in enumerate(ordered) if s.scene_id == new_scene.scene_id), None
    )
    if idx is None:
        raise AssembleError(f"scene_id {new_scene.scene_id}가 에피소드에 없음")

    seg = workdir / f"seg_{new_scene.scene_id:03d}.mp4"
    if not seg.exists():
        raise AssembleError(f"기존 세그먼트 없음: {seg} — 먼저 preset_longform_16x9 실행")
    render_scene_segment(
        new_scene, new_audio_path, seg, bible, fact_sheet,
        visual_path=new_visual_path,
    )

    all_segs = [workdir / f"seg_{s.scene_id:03d}.mp4" for s in ordered]
    before, after = all_segs[:idx], all_segs[idx + 1:]
    parts: list[Path] = []
    if before:
        head = workdir / "replace_head.mp4"
        _concat_plain(before, head, workdir)
        parts.append(head)
    parts.append(seg)
    if after:
        tail = workdir / "replace_tail.mp4"
        _concat_plain(after, tail, workdir)
        parts.append(tail)

    master = workdir / "master.mp4"
    if len(parts) == 1:
        _concat_plain(parts, master, workdir)
    else:
        _concat_with_boundary_xfade(parts, master)

    ordered_scenes = [new_scene if s.scene_id == new_scene.scene_id else s for s in ordered]
    total = probe_duration(master)
    chapters = _chapters_from_scenes(ordered_scenes)
    _embed_chapters_and_bgm(master, out_path, chapters, total, workdir, bgm_path)

    chapters_text = "\n".join(f"{_fmt_ts(t)} {name}" for name, t in chapters)
    return EpisodeRender(
        out_path=str(out_path), duration=round(total, 2),
        chapters_text=chapters_text, segment_paths=[str(p) for p in all_segs],
    )
