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


def _gen_demo_source(path: Path, n_shots: int = 6, shot_seconds: int = 4) -> None:
    """리캡 데모용 자체 제작 원본 — 색상이 다른 샷 n개 (라이선스: self-produced)."""
    # 고대비 색 — ffmpeg scene 점수(프레임 차분)가 임계값 0.4를 확실히 넘도록
    colors = ["0xC03030", "0x3080C0", "0x30A050", "0xE0C030", "0x8040B0", "0xE07030"]
    parts = []
    for i in range(n_shots):
        seg = path.parent / f"src_shot_{i}.mp4"
        subprocess.run([
            "ffmpeg", "-y", "-f", "lavfi",
            "-i", f"color=c={colors[i % len(colors)]}:s=1280x720:d={shot_seconds}",
            "-vf", (
                "drawtext=fontfile=/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc:"
                f"text='원본 샷 {i + 1}':fontsize=96:fontcolor=white:"
                "x=(w-text_w)/2:y=(h-text_h)/2"
            ),
            "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p", str(seg),
        ], check=True, capture_output=True)
        parts.append(seg)
    lst = path.parent / "src_concat.txt"
    lst.write_text("".join(f"file '{p.resolve()}'\n" for p in parts), encoding="utf-8")
    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(lst),
        "-c", "copy", str(path),
    ], check=True, capture_output=True)


DEMO_RECAP_STORY = (
    "한 남자가 폐쇄된 등대를 관리하러 섬에 도착했습니다. "
    "첫날 밤 등대 불빛이 저절로 꺼졌습니다. "
    "남자는 발전실로 내려가 스위치를 올렸습니다. "
    "벽에 전임자가 남긴 27개의 금이 새겨져 있었습니다. "
    "다음날 배가 오기로 한 날짜에 배가 오지 않았습니다. "
    "남자는 벽에 스물여덟 번째 금을 그었습니다."
)


def cmd_produce(args) -> None:
    """대본 파일 → 완성 영상 + 메타. 90일 시스템(plans/13)의 제작 표준 경로.

    대본 형식: 한 행 = 한 절(= 씬 = 자막). docs/prompts/02·03 출력 규격.
    """
    from tracks.recap.style_lint import apply_guideline_substitutions, lint_nyaong

    track = Track(args.track)
    bible = load_bible(track)
    script_path = Path(args.script)
    lines = [
        ln.strip() for ln in script_path.read_text(encoding="utf-8").splitlines()
        if ln.strip()
    ]
    if len(lines) < 3:
        raise SystemExit("대본이 3행 미만 — docs/prompts/02 출력 규격 확인")

    slug = args.slug or script_path.stem
    workdir = Path("data/assets/produce") / slug
    workdir.mkdir(parents=True, exist_ok=True)

    print(f"1) 대본 {len(lines)}행 → 씬 구성 + 스타일 검수")
    scenes = []
    for i, line in enumerate(lines):
        chapter = "훅" if i < 2 else ("마무리" if i == len(lines) - 1 else "본편")
        text = apply_guideline_substitutions(line)
        scenes.append(Scene(
            scene_id=i + 1, track=track, chapter=chapter,
            narration=text, caption=text[:38],
            visual=SceneVisual(
                type="slide", ref=f"produce/{slug}/{i + 1}",
                effect="kenburns" if i % 2 == 0 else "none",
            ),
            conte=Conte(
                info_point=text[:40],
                emotion=Emotion(tone="텐션 유지", delivery="빠르게, 행 끝 반 박자 쉼"),
                composition="중앙 구도, 하단 자막 여백",
                visual_direction=f"'{text[:30]}' 분위기의 삽화",
            ),
        ))
    issues = lint_nyaong(scenes)
    if issues:
        print("   ⚠ 스타일 린트 위반 (계속 진행, 해당 행 재생성 권장):")
        for it in issues[:8]:
            print(f"     - {it}")
    else:
        print("   린트 통과")

    print("2) TTS (실측 길이 기입)")
    sheet = FactSheet()
    audios = tts.synthesize_episode(scenes, bible, sheet, workdir / "audio")
    total = tts.total_duration(audios)
    print(f"   합계 {total:.0f}초 ({audios[0].backend})")

    print("3) 렌더")
    result = assemble.preset_longform_16x9(
        scenes, bible, sheet, workdir / "work", workdir / "episode.mp4",
        audio_paths={a.scene_id: a.path for a in audios},
        bgm_path=args.bgm or None,
    )
    outputs = [result.out_path]
    if args.shorts:
        shorts_path = assemble.preset_shorts(
            workdir / "work", [s.scene_id for s in scenes], workdir / "shorts.mp4",
        )
        outputs.append(shorts_path)
        print(f"   쇼츠(9:16) → {shorts_path}")

    meta = workdir / "meta.txt"
    meta.write_text(
        f"제목: {args.title}\n\n[설명란 초안 — docs/prompts/04로 확정]\n"
        f"{args.title}\n\n{result.chapters_text}\n\n#쇼츠 #스토리\n",
        encoding="utf-8",
    )
    print(f"   → {result.out_path} ({result.duration:.1f}s)")
    print(f"   → {meta} (제목·챕터·설명 초안)")


def cmd_recap_demo(args) -> None:
    from core import source_ingest
    from tracks.recap.nyaong_writer import write_recap
    from tracks.recap.style_lint import lint_nyaong

    bible = load_bible(Track.RECAP)
    workdir = DEMO_DIR / "recap"
    workdir.mkdir(parents=True, exist_ok=True)

    print("1) 자체 제작 데모 원본 생성 + 라이선스 게이트 통과 ingest")
    src = workdir / "source.mp4"
    _gen_demo_source(src)
    meta = source_ingest.ingest_source(
        str(src), "등대지기 (자체 제작 데모)",
        {"source": "self-produced", "license": "internal-demo", "permission_ref": "demo-001"},
        workdir, transcript=DEMO_RECAP_STORY,
    )
    print(f"   {meta.duration:.1f}s, 샷 {len(meta.shots)}개 감지")

    print("2) 이벤트 시퀀스 → 냐옹체 대본 (키 없으면 결정적 목)")
    events = source_ingest.events_from_transcript(meta.transcript)
    scenes = write_recap(events, meta.shots, bible, title=meta.title)
    issues = lint_nyaong(scenes)
    print(f"   씬 {len(scenes)}개, 스타일 린트: {'통과' if not issues else issues}")

    print("3) TTS + preset_recap 렌더 (컷 싱크 + 자막 + 2트랙)")
    manifest = Manifest(episode_id="recap-demo", track=Track.RECAP,
                        outline=meta.title, fact_sheet=FactSheet())
    audios = tts.synthesize_episode(scenes, bible, manifest.fact_sheet, workdir / "audio")
    result = assemble.preset_recap(
        scenes, bible, manifest.fact_sheet, meta.path, workdir / "work",
        workdir / "recap.mp4", audio_paths={a.scene_id: a.path for a in audios},
    )
    print(f"   → {result.out_path} ({result.duration:.1f}s)")

    print("4) 쇼츠 파생 (훅 씬 2개 → 9:16)")
    shorts = assemble.preset_shorts(workdir / "work", [1, 2], workdir / "shorts_01.mp4")
    print(f"   → {shorts}")


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

    p4 = sub.add_parser("recap-demo", help="리캡 트랙 e2e: 수집→냐옹체→컷싱크→쇼츠")
    p4.set_defaults(fn=cmd_recap_demo)

    p5 = sub.add_parser("produce", help="대본 파일 → 완성 영상+메타 (제작 표준 경로)")
    p5.add_argument("--script", required=True, help="대본 .txt (한 행 = 한 절)")
    p5.add_argument("--title", required=True)
    p5.add_argument("--track", default="recap", choices=[t.value for t in Track])
    p5.add_argument("--shorts", action="store_true", help="9:16 세로판 추가 생성")
    p5.add_argument("--bgm", default="", help="BGM 파일 (글로벌 -26 LUFS 언더베드)")
    p5.add_argument("--slug", default="", help="출력 폴더명 (기본: 대본 파일명)")
    p5.set_defaults(fn=cmd_produce)

    p3 = sub.add_parser("e2e", help="script→tts→assemble 전체 e2e")
    p3.add_argument("--track", default="japan", choices=[t.value for t in Track])
    p3.add_argument("--minutes", type=int, default=10)
    p3.add_argument("--outline", default="")
    p3.set_defaults(fn=cmd_e2e)

    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
