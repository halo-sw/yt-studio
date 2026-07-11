"""script.py 검증 — 프롬프트에 절대 규칙이 실제로 들어가는지 확인."""

from core.schemas import FactSheet, Manifest, Scene, SceneContext, SceneVisual, Track, load_bible
from core.script import (
    LengthSpec,
    build_regen_prompt,
    build_system_prompt,
    build_user_prompt,
    generate_script,
    lint_fact_rule,
    prompt_summary,
    validate_length,
)


def make_manifest(track=Track.JAPAN, minutes_facts=None):
    return Manifest(
        episode_id="ep-t1", track=track, outline="일본 20대 평균 연봉의 함정",
        chapters=["훅", "본론 1", "본론 2", "마무리"],
        fact_sheet=FactSheet(facts=minutes_facts or {"jp_avg_salary": 4_580_000}),
    )


def test_system_prompt_contains_absolute_rules():
    bible = load_bible(Track.JAPAN)
    spec = LengthSpec.for_minutes(12, Track.JAPAN)
    sp = build_system_prompt(Track.JAPAN, bible, spec)
    # 규칙 5-3: fact 토큰 강제 문구
    assert "{{fact:" in sp
    # 규칙 5-7: 씬 수·글자수·훅·미드롤 클리프행어
    assert f"{spec.min_scenes}~{spec.max_scenes}개" in sp
    assert "40초" in sp and "클리프행어" in sp
    # 바이블 주입: 금지어·용어집
    for phrase in bible.banned_phrases:
        assert phrase in sp
    for term in bible.glossary:
        assert term in sp


def test_drama_prompt_has_copyright_rules():
    bible = load_bible(Track.DRAMA)
    sp = build_system_prompt(Track.DRAMA, bible, LengthSpec.for_minutes(10, Track.DRAMA))
    # 규칙 5-5: 비평 중심 + 배우/스틸 금지
    assert "비평" in sp and "배우 실명" in sp and "스틸컷" in sp


def test_length_spec_scales():
    s10 = LengthSpec.for_minutes(10, Track.DRAMA)
    s60 = LengthSpec.for_minutes(60, Track.PLAYLIST)
    assert (s10.min_scenes, s10.max_scenes) == (26, 32)
    assert s60.min_scenes == 156  # 26 × 6
    assert s10.midrolls == (240, 420)  # 10분 영상엔 10분 미드롤 없음 (600 < 600 False)


def test_regen_prompt_injects_context_and_locks():
    bible = load_bible(Track.JAPAN)
    manifest = make_manifest()
    scene = Scene(
        scene_id=7, track=Track.JAPAN, chapter="본론 2",
        narration="젊은 세대가 국경을 넘기 시작한 이유입니다.", caption="해외 이직",
        visual=SceneVisual(type="illust", ref="x", effect="kenburns"),
        context=SceneContext(prev_tail="구매력이 달라졌습니다.", next_head="이 이야기는 일본만의 이야기가 아닙니다."),
    )
    rp = build_regen_prompt(scene, bible, manifest)
    # 규칙 5-2: prev_tail/next_head + 잠금 자산(금지어) 자동 주입
    assert "구매력이 달라졌습니다." in rp
    assert "일본만의 이야기가 아닙니다." in rp
    assert bible.banned_phrases[0] in rp
    assert "씬 하나만" in rp


def test_generate_mock_meets_length_spec():
    scenes, report = generate_script(make_manifest(), load_bible(Track.JAPAN),
                                     minutes=10, api_key=None)
    assert report.ok, report.issues
    assert scenes[0].context.prev_tail == ""      # 첫 씬
    assert scenes[1].context.prev_tail             # 중간 씬은 문맥 보유
    assert all("{{fact:" in s.narration for s in scenes)  # 규칙 5-3


def test_validate_length_flags_and_reinforces():
    short = [Scene(scene_id=i + 1, track=Track.JAPAN, chapter="훅" if i < 2 else "본론",
                   narration="너무 짧은 씬.", caption="",
                   visual=SceneVisual(type="slide", ref="x", effect="none"))
             for i in range(5)]
    report = validate_length(short, LengthSpec.for_minutes(10, Track.JAPAN))
    assert not report.ok
    assert report.reinforce_chapters  # 보강 챕터 지정 (규칙 5-7)


def test_lint_fact_rule_catches_raw_numbers():
    bad = Scene(scene_id=1, track=Track.JAPAN, chapter="훅",
                narration="평균 연봉은 4580000엔입니다.", caption="",
                visual=SceneVisual(type="slide", ref="x", effect="none"))
    good = Scene(scene_id=2, track=Track.JAPAN, chapter="훅",
                 narration="평균 연봉은 {{fact:jp_avg_salary}}엔입니다.", caption="",
                 visual=SceneVisual(type="slide", ref="x", effect="none"))
    assert lint_fact_rule([bad]) and not lint_fact_rule([good])


def test_prompt_summary_for_ui():
    s = prompt_summary(Track.JAPAN, load_bible(Track.JAPAN), LengthSpec.for_minutes(12, Track.JAPAN))
    assert s["banned_phrases"] and "fact" in s["fact_rule"]
