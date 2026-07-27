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
import re
import subprocess
import time
from pathlib import Path

from core import assemble, script, tts
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
    if getattr(args, "voice", ""):
        # 에피소드 단위 보이스 오버라이드 (옴니버스에서 사연별 화자 교차용).
        # 바이블은 frozen(잠금 자산) — 복사본으로 이번 실행만 덮어쓴다.
        # 캐시 서명에 voice_id가 들어가므로 교체 시 자동 재합성된다.
        bible = bible.model_copy(update={"voice_id": args.voice})
        print(f"   보이스 오버라이드: {bible.voice_id}")
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
    # 트랙 감정 아크(script.TRACK_STRUCTURES)를 씬 위치에 비례 배분 —
    # tts가 씬별 emotion_preset으로 매핑해 낭독 감정 낙차를 만든다.
    arc = [tone for _, _, tone in script.TRACK_STRUCTURES[track]]
    # 씬별 감정 톤 오버라이드 — {대본}.tones.json 이 있으면 아크 자동 배분보다 우선.
    # 트랙 기본 아크는 해당 트랙의 대표 포맷 하나를 전제로 균등 배분하므로,
    # 같은 트랙 안에서 감정 곡선이 다른 포맷(예: 심리 B형 유형 해부형 —
    # 피크가 앞쪽 '반전'에 있고 뒤쪽은 위로 구간)에는 맞지 않는다.
    # 형식: {"14": "호기심", "23": "차분"} — 미지정 씬은 아크 자동 배분.
    tone_map: dict[int, str] = {}
    tones_path = script_path.with_suffix(".tones.json")
    if tones_path.exists():
        import json as _json

        tone_map = {int(k): v for k, v in
                    _json.loads(tones_path.read_text(encoding="utf-8")).items()}
        print(f"   씬별 감정 톤 로드: {tones_path.name} ({len(tone_map)}개 씬)")
    static_ids = {int(x) for x in getattr(args, "static", "").split(",") if x.strip().isdigit()}
    scenes = []
    for i, line in enumerate(lines):
        chapter = "훅" if i < 2 else ("마무리" if i == len(lines) - 1 else "본편")
        text = apply_guideline_substitutions(line)
        tone = (tone_map.get(i + 1) or getattr(args, "tone", "")
                or arc[min(i * len(arc) // len(lines), len(arc) - 1)])
        scenes.append(Scene(
            scene_id=i + 1, track=track, chapter=chapter,
            narration=text, caption=text,  # 타임드 자막: 렌더가 문장 단위로 쪼갬
            visual=SceneVisual(
                type="slide", ref=f"produce/{slug}/{i + 1}",
                # 인포그래픽 슬라이드(--static)는 줌 금지 — 표·도표에 Ken Burns가 들어가면 부자연
                effect="none" if (i + 1) in static_ids else ("kenburns" if i % 2 == 0 else "none"),
            ),
            conte=Conte(
                info_point=text[:40],
                emotion=Emotion(tone=tone, delivery="빠르게, 행 끝 반 박자 쉼"),
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

    # 규칙 5-3: {script}.facts.json이 있으면 사실 시트로 로드 — 수치는 토큰으로만
    sheet = FactSheet()
    facts_path = script_path.with_suffix(".facts.json")
    if facts_path.exists():
        import json as _json

        sheet = FactSheet(facts=_json.loads(facts_path.read_text(encoding="utf-8")))
        print(f"   사실 시트 로드: {facts_path.name} ({len(sheet.facts)}개 키)")
    missing = [k for s in scenes for k in s.fact_refs() if k not in sheet.facts]
    if missing:
        raise SystemExit(f"사실 시트에 없는 키 (규칙 5-3): {sorted(set(missing))}")

    print("2) TTS (실측 길이 기입)")
    audio_dir = workdir / "audio"
    existing = sorted(audio_dir.glob("scene_*.wav")) if audio_dir.exists() else []
    if getattr(args, "reuse_audio", False) and len(existing) == len(scenes):
        # 대본이 안 바뀐 재렌더 — 기존 합성 결과 재사용 (TTS 재과금 방지)
        audios = []
        for s, wav in zip(scenes, existing):
            s.duration = tts.probe_duration(wav)
            audios.append(tts.SceneAudio(
                scene_id=s.scene_id, path=wav, duration=s.duration,
                chars=len(s.narration), backend="reused"))
        print(f"   기존 음성 {len(audios)}개 재사용 (--reuse-audio)")
    else:
        audios = tts.synthesize_episode(scenes, bible, sheet, audio_dir)
    total = tts.total_duration(audios)
    print(f"   합계 {total:.0f}초 ({audios[0].backend})")

    # 씬 이미지 드롭인: --images 폴더의 파일명 숫자 → scene_id 매핑
    # (예: 1.png, 003.jpg, scene_07.png). 없는 씬은 플레이스홀더 자동 생성.
    visual_paths: dict[int, Path] = {}
    if args.images:
        img_dir = Path(args.images)
        video_ext = {".mp4", ".mov", ".webm", ".mkv"}
        for f in sorted(img_dir.iterdir()):
            # 모션 클립(영상)도 씬 비주얼로 드롭인 가능 — 같은 파일명 숫자 규칙.
            # 같은 씬 번호에 이미지·영상이 둘 다 있으면 영상(모션)이 우선한다.
            if f.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", *video_ext}:
                m = re.search(r"(\d+)", f.stem)
                if not m:
                    continue
                sid = int(m.group(1))
                prev = visual_paths.get(sid)
                if prev is not None and prev.suffix.lower() in video_ext \
                        and f.suffix.lower() not in video_ext:
                    continue
                visual_paths[sid] = f
        print(f"   씬 이미지 {len(visual_paths)}개 매핑 (미지정 씬은 플레이스홀더)")

    print("3) 렌더")
    result = assemble.preset_longform_16x9(
        scenes, bible, sheet, workdir / "work", workdir / "episode.mp4",
        audio_paths={a.scene_id: a.path for a in audios},
        visual_paths=visual_paths or None,
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
        f"제목: {args.title}\n"
        f"트랙: {track.value}  ← 업로드 채널 확인용 (GUIDELINE §4-1-2 매핑표)\n\n"
        f"[설명란 초안 — GUIDELINE 3-6 메타 프롬프트로 확정]\n"
        f"{args.title}\n\n{result.chapters_text}\n\n#쇼츠 #스토리\n",
        encoding="utf-8",
    )

    # 편집 플랜(edit_plan.json) — CapCut 드래프트 자동 조립(tools/capcut_push.py)
    # 및 외부 에디터 연동용 타임라인 명세 (GUIDELINE §4-1-3)
    import json as _json

    cursor = 0.0
    plan_scenes = []
    for a in audios:
        s = next(sc for sc in scenes if sc.scene_id == a.scene_id)
        plan_scenes.append({
            "scene_id": a.scene_id,
            "start": round(cursor, 3),
            "end": round(cursor + a.duration, 3),
            "duration": round(a.duration, 3),
            "segment": str(workdir / "work" / f"seg_{a.scene_id:03d}.mp4"),
            "audio": str(a.path),
            "caption": s.caption,
            "narration": s.narration,
        })
        cursor += a.duration
    (workdir / "edit_plan.json").write_text(_json.dumps({
        "title": args.title, "track": track.value,
        "fps": 30, "width": 1920, "height": 1080,
        "total_duration": round(cursor, 3),
        "bgm": args.bgm or None,
        "scenes": plan_scenes,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"   → {result.out_path} ({result.duration:.1f}s)")
    print(f"   → {meta} (제목·챕터·설명 초안)")


def cmd_clip(args) -> None:
    """클리핑 레인 원커맨드: URL/파일 → 다운로드 → 클립 컷 → 냐옹체 대본
    → TTS → 자막 번인 → 컷싱크 편집 → 쇼츠 파생.

    허가 정보 3종(--license-source/--license/--permission-ref)이 없으면
    ingest 게이트에서 멈춘다 — 이 게이트가 채널을 지킨다 (규칙 5-5).
    """
    from core import source_ingest
    from tracks.recap.nyaong_writer import write_recap
    from tracks.recap.style_lint import lint_nyaong

    bible = load_bible(Track.RECAP)
    slug = args.slug or "clip_" + re.sub(r"[^a-zA-Z0-9가-힣]+", "_", args.title)[:30]
    workdir = Path("data/assets/produce") / slug
    workdir.mkdir(parents=True, exist_ok=True)

    print("1) 원본 수집 (라이선스 게이트 → 다운로드 → 샷 감지)")
    transcript = ""
    if args.transcript:
        transcript = Path(args.transcript).read_text(encoding="utf-8")
    meta = source_ingest.ingest_source(
        args.source, args.title,
        {
            "source": args.license_source,
            "license": args.license,
            "permission_ref": args.permission_ref,
        },
        workdir, transcript=transcript,
    )
    print(f"   {meta.duration:.1f}s, 샷 {len(meta.shots)}개")

    print("2) 이벤트 시퀀스 → 냐옹체 대본")
    if not meta.transcript:
        raise SystemExit(
            "자막/줄거리 텍스트가 필요합니다: --transcript 파일 지정\n"
            "(원본 자막 덤프 또는 시간순 사건 요약 — 이것이 대본의 원재료)"
        )
    events = source_ingest.events_from_transcript(meta.transcript)
    scenes = write_recap(events, meta.shots, bible, title=meta.title)
    issues = lint_nyaong(scenes)
    print(f"   씬 {len(scenes)}개, 린트: {'통과' if not issues else issues[:4]}")

    print("3) TTS → 컷싱크 렌더 (자막 번인 + 2트랙)")
    sheet = FactSheet()
    audios = tts.synthesize_episode(scenes, bible, sheet, workdir / "audio")
    result = assemble.preset_recap(
        scenes, bible, sheet, meta.path, workdir / "work", workdir / "episode.mp4",
        audio_paths={a.scene_id: a.path for a in audios},
        bgm_path=args.bgm or None,
    )
    print(f"   → {result.out_path} ({result.duration:.1f}s)")

    if args.shorts:
        n = min(3, len(scenes))
        shorts = assemble.preset_shorts(
            workdir / "work", [s.scene_id for s in scenes[:n]], workdir / "shorts.mp4",
        )
        print(f"4) 쇼츠(9:16, 훅 {n}씬) → {shorts}")

    (workdir / "meta.txt").write_text(
        f"제목: {args.title}\n원본: {args.source}\n"
        f"허가: {args.license_source} / {args.license} / {args.permission_ref}\n\n"
        f"{result.chapters_text}\n", encoding="utf-8",
    )
    print(f"   메타 → {workdir / 'meta.txt'}")


_WRITE_SYSTEM = """너는 스토리텔링 쇼츠 채널의 작가다. 채널 정체성은 "돈과 사람이 얽힌 반전 사연"이다.
규칙 (예외 없음):
- 첫 출력 행은 `제목: ...` 한 줄 (숫자형/모순형/결과형 중 하나, 대본에 없는 것 약속 금지). 그 다음 빈 줄, 그 다음 대본.
- 대본은 한 행 = 한 절. 연결어(~했는데/~했고/~하자/~했죠/~했습니다)마다 행을 바꾼다.
- 15~20행. 존댓말 고정. 행동 중심, 내면 묘사 금지. 실존 작품·실화 재현 금지.
- 연결어 분포: 했는데 40% / 했고 25% / 하자 15% / 했죠 10% / 했습니다 5%. 같은 연결어 3연속 금지.
- "관객/시청자/보는 사람들" 언급 절대 금지.
- 첫 행 = 가장 강한 문장(구체 수치·시간/모순/인물갈등 중 2개 이상). 마지막 행 = 댓글 유도 질문.
- 죽었다→세상을 떠났다, 살해→제거, 시체→쓰러진 사람.
- 실제 통계 인용 시 {{fact:키이름}} 토큰으로만.
- 제목 줄과 대본 행 외에 어떤 텍스트도 출력하지 않는다 (번호·해설·빈말 금지)."""


def _claude_write(topic: str, feedback: str = "") -> tuple[str, list[str]]:
    """Claude API로 대본 생성 → (제목, 대본 행들). ANTHROPIC_API_KEY 필요."""
    import os

    import requests

    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        raise SystemExit(
            "ANTHROPIC_API_KEY가 없습니다 (.env에 추가).\n"
            "키 없이 쓰려면: Claude 앱에 GUIDELINE §B6 프롬프트를 붙여 대본을 만들고\n"
            "data/scripts/파일.txt로 저장 → produce/batch로 렌더하세요."
        )
    user = f"[소재]\n{topic}\n\n위 소재로 60~90초 대본을 규칙대로 써라."
    if feedback:
        user += f"\n\n[직전 출력의 린트 위반 — 반드시 해소하고 다시 써라]\n{feedback}"
    resp = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={"x-api-key": key, "anthropic-version": "2023-06-01",
                 "content-type": "application/json"},
        json={"model": "claude-sonnet-5", "max_tokens": 2000,
              "system": _WRITE_SYSTEM,
              "messages": [{"role": "user", "content": user}]},
        timeout=120,
    )
    if resp.status_code != 200:
        raise SystemExit(f"Claude API {resp.status_code}: {resp.text[:200]}")
    text = resp.json()["content"][0]["text"].strip()
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    title = ""
    if lines and lines[0].startswith("제목:"):
        title = lines[0].split(":", 1)[1].strip()
        lines = lines[1:]
    return title, lines


def cmd_write(args) -> None:
    """대본 자동 생성: 소재 한 줄 → Claude 생성 → 린트 자동 검수(위반 시 1회
    자동 재생성) → data/scripts/ 저장 → (--render 시 영상까지 원샷)."""
    import argparse as _ap

    from tracks.recap.style_lint import lint_nyaong

    def _lint(lines: list[str]) -> list[str]:
        scenes = [Scene(scene_id=i + 1, track=Track.RECAP, chapter="본편",
                        narration=ln, caption=ln[:30],
                        visual=SceneVisual(type="slide", ref="x"))
                  for i, ln in enumerate(lines)]
        return lint_nyaong(scenes)

    print("1) 대본 생성 (Claude)")
    title, lines = _claude_write(args.topic)
    issues = _lint(lines)
    if issues:
        print(f"   린트 위반 {len(issues)}건 → 자동 재생성")
        title2, lines2 = _claude_write(args.topic, feedback="\n".join(issues))
        if len(_lint(lines2)) <= len(issues):
            title, lines = (title2 or title), lines2
        issues = _lint(lines)

    out = Path(args.out or f"data/scripts/{args.slug}.txt")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    final_title = args.title or title or args.slug
    print(f"   → {out} ({len(lines)}행) / 제목: {final_title}")
    print(f"   린트: {'통과' if not issues else f'잔여 {len(issues)}건 — 해당 행 수동 확인: ' + '; '.join(issues[:3])}")

    if args.render:
        ns = _ap.Namespace(script=str(out), title=final_title, track=args.track,
                           shorts=True, bgm=args.bgm, images="", slug=args.slug)
        cmd_produce(ns)


def cmd_ui(args) -> None:
    """로컬 웹 UI — 대본 재고·생성·갤러리·지표 4화면 (Astryx 디자인 언어)."""
    import uvicorn

    print(f"yt-studio-multi UI → http://127.0.0.1:{args.port}  (종료: Ctrl+C)")
    uvicorn.run("service.api.app:app", host="127.0.0.1", port=args.port, log_level="warning")


def _release_dir(slug: str, workdir: Path) -> Path:
    """완성본이 갈 곳 — 트랙에 채널이 있으면 channels/<채널>/롱폼/, 없으면 data/releases/.

    트랙은 edit_plan.json의 씬에서 읽고, 채널 매핑은 data/channels.yaml의 dir 필드.
    """
    import json as _json

    import yaml as _yaml

    try:
        plan = _json.loads((workdir / "edit_plan.json").read_text(encoding="utf-8"))
        track = plan.get("track") or (plan.get("scenes") or [{}])[0].get("track")
        info = _yaml.safe_load(Path("data/channels.yaml").read_text(encoding="utf-8")).get(track)
        if info and info.get("dir"):
            return Path(info["dir"]) / "롱폼" / slug
    except (OSError, ValueError, KeyError, IndexError, AttributeError):
        pass
    return Path("data/releases") / slug


def cmd_release(args) -> None:
    """제작 산출물을 발행용 단일 폴더로 수집.

    트랙에 연결된 채널이 있으면 channels/<채널>/롱폼/<슬러그>/,
    없으면 data/releases/<슬러그>/. 영상(인트로 결합본 우선) + 썸네일 +
    업로드 텍스트를 한곳에 모아 업로드할 때 폴더 하나만 열면 되게 한다.
    """
    import shutil

    slug = args.slug
    workdir = Path("data/assets/produce") / slug
    if not workdir.exists():
        raise SystemExit(f"제작 폴더 없음: {workdir}")
    out = _release_dir(slug, workdir)
    out.mkdir(parents=True, exist_ok=True)

    # 영상: --video 지정 > 인트로 결합본 > 기본 렌더본
    video = Path(args.video) if args.video else None
    if video is None:
        for cand in ("episode_with_intro.mp4", "episode.mp4"):
            if (workdir / cand).exists():
                video = workdir / cand
                break
    if video is None or not video.exists():
        raise SystemExit(f"영상 파일 없음: {workdir}/episode*.mp4")
    shutil.copy2(video, out / f"{slug}.mp4")

    # 썸네일: --thumb 지정 > thumbs/thumb_A.png
    thumb = Path(args.thumb) if args.thumb else workdir / "thumbs" / "thumb_A.png"
    if thumb.exists():
        shutil.copy2(thumb, out / f"{slug}_thumbnail.png")

    # 업로드 텍스트: upload.txt > meta.txt
    for cand in ("upload.txt", "meta.txt"):
        if (workdir / cand).exists():
            shutil.copy2(workdir / cand, out / f"{slug}_upload.txt")
            break

    print(f"릴리스 수집 완료 → {out}/")
    for f in sorted(out.iterdir()):
        print(f"   {f.name} ({f.stat().st_size // 1024:,}KB)")


def cmd_batch(args) -> None:
    """배치 렌더: 큐 파일(YAML) 한 번 실행으로 여러 트랙(채널) 영상 일괄 산출.

    큐 항목: {script, title, track?, shorts?, bgm?, images?, slug?}
    한 편 실패해도 멈추지 않고 다음으로 — 마지막에 성공/실패 리포트.
    """
    import argparse as _ap

    import yaml

    queue = yaml.safe_load(Path(args.queue).read_text(encoding="utf-8"))
    if not isinstance(queue, list) or not queue:
        raise SystemExit("큐 형식: 항목 리스트 YAML (GUIDELINE §4-1-2)")

    results = []
    for i, item in enumerate(queue, 1):
        print(f"\n===== [{i}/{len(queue)}] {item.get('title', item.get('script'))} =====")
        ns = _ap.Namespace(
            script=item["script"], title=item["title"],
            track=item.get("track", "recap"),
            shorts=bool(item.get("shorts", True)),
            bgm=item.get("bgm", ""), images=item.get("images", ""),
            slug=item.get("slug", ""),
        )
        try:
            cmd_produce(ns)
            results.append((item["title"], "OK"))
        except SystemExit as e:
            results.append((item["title"], f"실패: {e}"))
        except Exception as e:
            results.append((item["title"], f"실패: {type(e).__name__}: {str(e)[:80]}"))

    print("\n===== 배치 결과 =====")
    ok = sum(1 for _, s in results if s == "OK")
    for title, status in results:
        print(f"  {'✅' if status == 'OK' else '❌'} {title} — {status}")
    print(f"성공 {ok}/{len(results)}")


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


def _load_dotenv(path: Path = Path(".env")) -> None:
    """가벼운 .env 로더 — 키는 레포에 커밋하지 않고 여기서만 읽는다."""
    import os

    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())


def main() -> None:
    _load_dotenv()
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

    p6 = sub.add_parser("clip", help="클리핑 레인: URL/파일→다운로드→클립→자막·TTS→편집→쇼츠")
    p6.add_argument("--source", required=True, help="영상 URL(yt-dlp) 또는 로컬 파일")
    p6.add_argument("--title", required=True)
    p6.add_argument("--license-source", required=True, help="권리자/출처 (예: 제작사명)")
    p6.add_argument("--license", required=True, help="라이선스 종류 (예: CC-BY, 제휴계약)")
    p6.add_argument("--permission-ref", required=True, help="허가 근거 (계약ID/CC URL/자체제작)")
    p6.add_argument("--transcript", default="", help="자막 덤프 또는 사건 요약 텍스트 파일")
    p6.add_argument("--shorts", action="store_true")
    p6.add_argument("--bgm", default="")
    p6.add_argument("--slug", default="")
    p6.set_defaults(fn=cmd_clip)

    p5 = sub.add_parser("produce", help="대본 파일 → 완성 영상+메타 (제작 표준 경로)")
    p5.add_argument("--script", required=True, help="대본 .txt (한 행 = 한 절)")
    p5.add_argument("--title", required=True)
    p5.add_argument("--track", default="recap", choices=[t.value for t in Track])
    p5.add_argument("--shorts", action="store_true", help="9:16 세로판 추가 생성")
    p5.add_argument("--bgm", default="", help="BGM 파일 (글로벌 -26 LUFS 언더베드)")
    p5.add_argument("--images", default="", help="씬 이미지 폴더 (파일명 숫자=씬 번호, 미지정 씬은 플레이스홀더)")
    p5.add_argument("--voice", default="",
                    help="Typecast voice_id 오버라이드 (기본: 트랙 바이블 voice_id)")
    p5.add_argument("--tone", default="",
                    help="전 씬 감정 톤 강제 (예: '여운'→tonedown — 프레임 내레이션 등 톤 통일용)")
    p5.add_argument("--reuse-audio", action="store_true", dest="reuse_audio",
                    help="대본이 같을 때 기존 합성 음성 재사용 (TTS 재과금 방지)")
    p5.add_argument("--slug", default="", help="출력 폴더명 (기본: 대본 파일명)")
    p5.add_argument("--static", default="",
                    help="줌(Ken Burns) 없이 정지로 보여줄 씬 번호 (쉼표 구분, 인포그래픽 슬라이드용)")
    p5.set_defaults(fn=cmd_produce)

    p11 = sub.add_parser("bbogaegi", help="공고 뽀개기 하네스: 에피소드 YAML → 발행 산출물 원샷 (realestate)")
    p11.add_argument("--episode", required=True, help="에피소드 정의 YAML (data/episodes/<슬러그>.yaml)")
    p11.add_argument("--skip-visuals", action="store_true", dest="skip_visuals",
                     help="Higgsfield 생성 건너뜀 (기존 컷 재사용 — 크레딧 0 재렌더)")
    p11.set_defaults(fn=lambda args: __import__(
        "tracks.realestate.bbogaegi", fromlist=["run"]).run(args.episode, args.skip_visuals))

    p10 = sub.add_parser("release", help="영상+썸네일+업로드 텍스트를 채널 서랍(channels/<채널>/롱폼/) 또는 data/releases/로 수집")
    p10.add_argument("--slug", required=True, help="제작 폴더명 (data/assets/produce/<슬러그>)")
    p10.add_argument("--video", default="", help="영상 직접 지정 (기본: 인트로 결합본 우선 자동 선택)")
    p10.add_argument("--thumb", default="", help="썸네일 직접 지정 (기본: thumbs/thumb_A.png)")
    p10.set_defaults(fn=cmd_release)

    p9 = sub.add_parser("ui", help="로컬 웹 UI 실행 (http://127.0.0.1:8787)")
    p9.add_argument("--port", type=int, default=8787)
    p9.set_defaults(fn=cmd_ui)

    p8 = sub.add_parser("write", help="소재 한 줄 → 대본 자동 생성(린트 자동 재시도) → (--render 시 영상까지)")
    p8.add_argument("--topic", required=True, help="소재: 로그라인 / 반전 / 마지막 질문")
    p8.add_argument("--slug", required=True, help="대본 파일명 (data/scripts/{slug}.txt)")
    p8.add_argument("--title", default="", help="제목 (미지정 시 Claude 생성 제목 사용)")
    p8.add_argument("--track", default="recap", choices=[t.value for t in Track])
    p8.add_argument("--out", default="", help="저장 경로 (기본 data/scripts/{slug}.txt)")
    p8.add_argument("--bgm", default="")
    p8.add_argument("--render", action="store_true", help="생성 직후 영상까지 원샷")
    p8.set_defaults(fn=cmd_write)

    p7 = sub.add_parser("batch", help="큐 YAML 1회 실행 → 여러 트랙 영상 일괄 렌더")
    p7.add_argument("--queue", required=True, help="큐 파일 (예: data/scripts/batch_week1.yaml)")
    p7.set_defaults(fn=cmd_batch)

    p3 = sub.add_parser("e2e", help="script→tts→assemble 전체 e2e")
    p3.add_argument("--track", default="japan", choices=[t.value for t in Track])
    p3.add_argument("--minutes", type=int, default=10)
    p3.add_argument("--outline", default="")
    p3.set_defaults(fn=cmd_e2e)

    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
