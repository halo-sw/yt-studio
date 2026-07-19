"""cli.py — M1 파이프라인 e2e CLI: script → tts → assemble.

API 키가 하나도 없어도 끝까지 돈다 (script는 목 생성기, tts는 espeak-ng 폴백,
비주얼은 플레이스홀더 — M1 허용 범위). 키가 있으면 자동으로 실 API를 쓴다.

사용:
  python cli.py playlist-demo            # 샘플 곡 3개 → 미니 플레이리스트 렌더
  python cli.py longform-demo            # 씬 3개 롱폼 렌더 (BGM 언더베드 포함)
  python cli.py longform-demo --replace  # 렌더 후 2번 씬 교체 재조립 비교
  python cli.py e2e --track japan --minutes 12   # 대본→TTS→조립 전체 e2e
"""

from __future__ import annotations

import argparse
import subprocess
import time
from pathlib import Path

from core import assemble, tts
from core.schemas import (
    Conte, Emotion, FactSheet, Manifest, Scene, SceneVisual, Track, load_bible,
)
from core.script import LengthSpec, generate_script, validate_length
from tracks.playlist.library import Song, to_assemble_inputs

DEMO_DIR = Path("data/assets/demo")


def _gen_sample_song(path: Path, freq: float, seconds: int = 60) -> None:
    """검증용 샘플 곡 — 배음 2개 + 트레몰로 + 페이드 (라이선스: 자체 생성)."""
    expr = (
        f"0.28*sin(2*PI*{freq}*t)+0.14*sin(2*PI*{freq * 1.5}*t)"
        f"+0.07*sin(2*PI*{freq * 2}*t)"
    )
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi",
        "-i", f"aevalsrc={expr}:d={seconds}:s=44100",
        "-af", f"tremolo=f=0.5:d=0.3,afade=in:d=2,afade=out:st={seconds - 3}:d=3",
        "-c:a", "aac", str(path),
    ], check=True, capture_output=True)


def cmd_playlist_demo(args) -> None:
    workdir = DEMO_DIR / "playlist"
    workdir.mkdir(parents=True, exist_ok=True)
    print("1) 샘플 곡 3개 생성 (자체 생성 → 라이선스 메타 self-produced)")
    freqs = [220.0, 261.63, 329.63]
    songs = []
    for i, f in enumerate(freqs):
        p = workdir / f"song_{i + 1}.m4a"
        _gen_sample_song(p, f, seconds=args.song_seconds)
        songs.append(Song(
            path=str(p), title=f"Demo Mood {i + 1}", artist="channel-factory",
            license_meta={"source": "self-produced", "license": "internal-demo"},
        ))

    print("2) 루프 비주얼 플레이스홀더 생성")
    visual = assemble.make_placeholder_image(
        "Rainy Window Mood", workdir / "loop_art.png",
        subtitle="demo loop visual", palette=1,
    )

    print("3) preset_playlist_1h 렌더 (loudnorm → 크로스페이드 → 루프 비주얼)")
    t0 = time.time()
    result = assemble.preset_playlist_1h(
        to_assemble_inputs(songs), visual,
        workdir / "mini_playlist.mp4", workdir / "work",
    )
    print(f"   완료 {time.time() - t0:.1f}s → {result.out_path} ({result.duration:.1f}s)")
    print("--- 유튜브 설명란 타임스탬프 ---")
    print(result.timestamps)


def _demo_scenes() -> tuple[Manifest, list[Scene]]:
    manifest = Manifest(
        episode_id="demo-ep-001", track=Track.JAPAN,
        outline="일본 20대 평균 연봉의 함정",
        chapters=["훅", "케이스 계산 A/B", "체크리스트"],
        fact_sheet=FactSheet(facts={
            "jp_avg_salary": 4_580_000, "case_a_takehome": 3_120_000,
            "case_b_takehome": 3_540_000,
        }),
    )
    mk = lambda i, ch, narr, cap, effect: Scene(
        scene_id=i, track=Track.JAPAN, chapter=ch, narration=narr, caption=cap,
        visual=SceneVisual(type="slide", ref=f"demo/scene_{i}", effect=effect),
        conte=Conte(
            info_point=f"{ch} 핵심", emotion=Emotion(tone="차분", delivery="보통 속도"),
            composition="와이드 샷, 하단 자막 여백", visual_direction=f"{ch} 슬라이드",
        ),
    )
    scenes = [
        mk(1, "훅",
           "일본 직장인의 평균 연봉은 {{fact:jp_avg_salary}}엔입니다. 그런데 실수령액을 계산해 보면 이야기가 완전히 달라집니다.",
           "평균 연봉 {{fact:jp_avg_salary}}엔의 함정", "kenburns"),
        mk(2, "케이스 계산 A/B",
           "케이스 A는 실수령 {{fact:case_a_takehome}}엔, 케이스 B는 {{fact:case_b_takehome}}엔. 같은 연봉인데 왜 이렇게 차이가 날까요.",
           "A {{fact:case_a_takehome}}엔 vs B {{fact:case_b_takehome}}엔", "none"),
        mk(3, "체크리스트",
           "오늘 확인할 것은 세 가지입니다. 공제 항목, 거주 지역, 그리고 부양 가족 등록 여부입니다. 다음 화에서 케이스 C를 다룹니다.",
           "체크리스트 3가지", "kenburns"),
    ]
    return manifest, scenes


def cmd_longform_demo(args) -> None:
    bible = load_bible(Track.JAPAN)
    manifest, scenes = _demo_scenes()
    workdir = DEMO_DIR / "longform"
    audio_dir = workdir / "audio"

    print("1) TTS (espeak-ng 폴백 또는 ElevenLabs)")
    audios = tts.synthesize_episode(scenes, bible, manifest.fact_sheet, audio_dir)
    for a in audios:
        print(f"   scene {a.scene_id}: {a.duration:.1f}s ({a.backend}, {a.chars}자)")
    audio_paths = {a.scene_id: a.path for a in audios}

    print("2) BGM 언더베드 샘플 생성 (-26 LUFS 글로벌 트랙)")
    bgm = workdir / "bgm.m4a"
    _gen_sample_song(bgm, 174.61, seconds=30)

    print("3) preset_longform_16x9 렌더 (Ken Burns + 자막 번인 + 2트랙 믹스 + 챕터)")
    t0 = time.time()
    result = assemble.preset_longform_16x9(
        scenes, bible, manifest.fact_sheet, workdir / "work",
        workdir / "episode.mp4", audio_paths=audio_paths, bgm_path=bgm,
    )
    print(f"   완료 {time.time() - t0:.1f}s → {result.out_path} ({result.duration:.1f}s)")
    print("--- 챕터 마커 ---")
    print(result.chapters_text)

    if args.replace:
        print("4) 씬 2 교체 (규칙 5-2: 해당 세그먼트만 재렌더 + 경계 80ms 크로스페이드)")
        new_scene = scenes[1].model_copy(deep=True)
        new_scene.narration = (
            "다시 계산해 보겠습니다. 케이스 A의 실수령은 {{fact:case_a_takehome}}엔, "
            "케이스 B는 {{fact:case_b_takehome}}엔. 차이의 정체는 공제 구조에 있습니다."
        )
        new_scene.duration = None
        audio = tts.synthesize_scene(
            new_scene, bible, manifest.fact_sheet, audio_dir / "regen", is_regen=True,
        )
        t0 = time.time()
        replaced = assemble.replace_scene(
            scenes, new_scene, bible, manifest.fact_sheet, workdir / "work",
            workdir / "episode_v2.mp4", new_audio_path=audio.path, bgm_path=bgm,
        )
        print(f"   완료 {time.time() - t0:.1f}s → {replaced.out_path} ({replaced.duration:.1f}s)")
        print("--- 교체 후 챕터 ---")
        print(replaced.chapters_text)


def cmd_e2e(args) -> None:
    track = Track(args.track)
    bible = load_bible(track)
    manifest = Manifest(
        episode_id=f"e2e-{track.value}", track=track,
        outline=args.outline or f"{track.value} e2e 검증 에피소드",
        chapters=[], fact_sheet=FactSheet(facts={"sample_metric": 42}),
    )
    print(f"1) 대본 생성 ({args.minutes}분 목표)")
    scenes, report = generate_script(manifest, bible, minutes=args.minutes)
    print(f"   씬 {report.scene_count}개 / {report.total_chars:,}자 / ok={report.ok}")

    print("2) TTS 실측")
    workdir = DEMO_DIR / f"e2e_{track.value}"
    audios = tts.synthesize_episode(scenes, bible, manifest.fact_sheet, workdir / "audio")
    total = tts.total_duration(audios)
    spec = LengthSpec.for_minutes(args.minutes, track)
    print(f"   실측 합계 {total / 60:.1f}분 (목표 {args.minutes}분)")
    if total < args.minutes * 60 * 0.9:
        report = validate_length(scenes, spec)
        print(f"   보강 필요 챕터: {report.reinforce_chapters} (규칙 5-7)")

    print("3) 조립")
    result = assemble.preset_longform_16x9(
        scenes, bible, manifest.fact_sheet, workdir / "work",
        workdir / "episode.mp4",
        audio_paths={a.scene_id: a.path for a in audios},
    )
    print(f"   → {result.out_path} ({result.duration / 60:.1f}분)")
    print(result.chapters_text)


def main() -> None:
    ap = argparse.ArgumentParser(description="channel-factory M1 파이프라인 CLI")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p1 = sub.add_parser("playlist-demo", help="샘플 곡 3개 → 미니 플레이리스트")
    p1.add_argument("--song-seconds", type=int, default=60)
    p1.set_defaults(fn=cmd_playlist_demo)

    p2 = sub.add_parser("longform-demo", help="씬 3개 롱폼 + (--replace) 씬 교체 비교")
    p2.add_argument("--replace", action="store_true")
    p2.set_defaults(fn=cmd_longform_demo)

    p3 = sub.add_parser("e2e", help="script→tts→assemble 전체 e2e")
    p3.add_argument("--track", default="japan", choices=[t.value for t in Track])
    p3.add_argument("--minutes", type=int, default=10)
    p3.add_argument("--outline", default="")
    p3.set_defaults(fn=cmd_e2e)

    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
