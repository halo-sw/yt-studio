"""tts.py 검증 — espeak-ng 폴백, fact 치환, 길이 실측."""

import shutil

import pytest

from core.schemas import FactSheet, Scene, SceneVisual, Track, load_bible
from core.tts import TTSError, resolve_fact_tokens, synthesize_scene

needs_espeak = pytest.mark.skipif(
    shutil.which("espeak-ng") is None or shutil.which("ffprobe") is None,
    reason="espeak-ng/ffprobe 필요",
)


def make_scene(narration="테스트 문장입니다.", caption=""):
    return Scene(
        scene_id=1, track=Track.JAPAN, chapter="훅", narration=narration,
        caption=caption, visual=SceneVisual(type="slide", ref="x"),
    )


def test_resolve_fact_tokens_substitutes():
    sheet = FactSheet(facts={"salary": 4_580_000, "rate": "12.5%"})
    out = resolve_fact_tokens("연봉 {{fact:salary}}엔, 세율 {{fact:rate}}", sheet)
    assert out == "연봉 4,580,000엔, 세율 12.5%"


def test_resolve_fact_tokens_missing_key_fails():
    # 규칙 5-3: 시트에 없는 키는 침묵 통과 대신 즉시 실패
    with pytest.raises(TTSError, match="없는 키"):
        resolve_fact_tokens("{{fact:ghost}}", FactSheet(facts={}))


@needs_espeak
def test_espeak_fallback_fills_duration(tmp_path):
    scene = make_scene("평균 연봉은 {{fact:salary}}엔입니다.")
    bible = load_bible(Track.JAPAN)
    sheet = FactSheet(facts={"salary": 4_580_000})
    audio = synthesize_scene(scene, bible, sheet, tmp_path, api_key=None)
    assert audio.backend == "espeak"
    assert audio.path.exists()
    assert scene.duration is not None and scene.duration > 0.5  # 실측 기입 (규칙 5-7)
    assert audio.chars == len("평균 연봉은 4,580,000엔입니다.")


@needs_espeak
def test_usage_logged_with_regen_flag(tmp_path):
    # 규칙 5-8: 재생성 크레딧 별도 집계 (is_regen=True)
    from core.models import UsageLogModel, create_all, get_engine, get_sessionmaker

    engine = get_engine(f"sqlite:///{tmp_path}/t.db")
    create_all(engine)
    session = get_sessionmaker(engine)()
    scene = make_scene()
    bible = load_bible(Track.JAPAN)
    synthesize_scene(
        scene, bible, FactSheet(), tmp_path, is_regen=True,
        session=session, episode_id="ep-1",
    )
    row = session.query(UsageLogModel).one()
    assert row.is_regen is True and row.units == len(scene.narration)
