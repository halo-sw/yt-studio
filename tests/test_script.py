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
    assert "훅" in s["structure"] and "긴장 피크" in s["emotion_arc"]


# ── 콘테 (v5 보고서: 정보전달·감정전달·구도·시각) ──

def test_system_prompt_contains_structure_and_conte_rules():
    from core.script import lint_conte
    bible = load_bible(Track.JAPAN)
    sp = build_system_prompt(Track.JAPAN, bible, LengthSpec.for_minutes(12, Track.JAPAN))
    # 트랙 구성 블루프린트 (보고서 §3 ①)
    assert "케이스 계산 A/B" in sp and "함정·반전" in sp and "체크리스트" in sp
    # 감정 아크 + 콘테 4요소 규칙
    assert "긴장 피크" in sp
    assert "info_point" in sp and "delivery" in sp
    assert "샷 사이즈 3연속 금지" in sp or "3연속 금지" in sp
    assert "댓글 유도" in sp  # 공통 길이 공학: 마지막 챕터 댓글 유도


def test_drama_structure_is_critique_shaped():
    sp = build_system_prompt(Track.DRAMA, load_bible(Track.DRAMA),
                             LengthSpec.for_minutes(12, Track.DRAMA))
    assert "콜드오픈" in sp and "반전 분석" in sp and "대안 시나리오" in sp


def test_mock_scenes_have_full_conte():
    from core.script import lint_conte
    scenes, report = generate_script(make_manifest(), load_bible(Track.JAPAN),
                                     minutes=10, api_key=None)
    assert report.ok
    issues = lint_conte(scenes)
    assert issues == [], issues  # 4요소 완비 + 샷/타입 리듬 + 정보 중복 없음
    s = scenes[0]
    assert s.conte.info_point and s.conte.emotion.tone and s.conte.emotion.delivery
    assert s.conte.composition and s.conte.visual_direction
    # 감정 아크가 구성표를 따름: 훅 씬은 궁금증 계열
    assert "궁금증" in scenes[0].conte.emotion.tone


def test_lint_conte_catches_rhythm_violations():
    from core.script import lint_conte
    from core.schemas import Conte, Emotion, SceneVisual, Scene
    def sc(i, shot, vtype):
        return Scene(scene_id=i, track=Track.JAPAN, chapter="훅",
                     narration="테스트.", caption="",
                     visual=SceneVisual(type=vtype, ref="x", effect="none"),
                     conte=Conte(info_point=f"p{i}", emotion=Emotion(tone="t", delivery="d"),
                                 composition=f"{shot} 샷", visual_direction="v"))
    bad = [sc(1, "와이드", "slide"), sc(2, "와이드", "slide"), sc(3, "와이드", "slide")]
    issues = lint_conte(bad)
    assert any("컷 리듬" in i for i in issues)
    assert any("3연속" in i and "slide" in i for i in issues)
    good = [sc(1, "와이드", "slide"), sc(2, "미디엄", "illust"), sc(3, "클로즈업", "chart")]
    assert lint_conte(good) == []
