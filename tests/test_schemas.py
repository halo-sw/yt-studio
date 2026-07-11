"""M0 검증 — 핵심 모델 3종 + 바이블 yaml 5개 로드."""

import pytest
from pydantic import ValidationError

from core.schemas import (
    Bible,
    Card,
    CastCard,
    FactSheet,
    Manifest,
    Scene,
    SceneContext,
    SceneVisual,
    Track,
    load_bible,
)


def make_scene(**overrides) -> Scene:
    base = dict(
        scene_id=1,
        track=Track.JAPAN,
        chapter="hook",
        narration="일본 평균 연봉은 {{fact:jp_avg_salary}}엔입니다.",
        caption="평균 연봉 {{fact:jp_avg_salary}}엔",
        visual=SceneVisual(type="chart", ref="assets/chart_01.png", effect="zoom_callout"),
        context=SceneContext(prev_tail="", next_head="그런데 이 수치에는 함정이 있죠."),
    )
    base.update(overrides)
    return Scene(**base)


def test_scene_duration_starts_none():
    # duration은 tts.py 실측 전까지 None (CLAUDE.md 4장)
    assert make_scene().duration is None


def test_scene_fact_refs():
    # 규칙 5-3: 수치는 {{fact:key}} 참조 — 키 추출 확인
    assert make_scene().fact_refs() == ["jp_avg_salary", "jp_avg_salary"]


def test_manifest_flags_missing_fact_keys():
    manifest = Manifest(
        episode_id="ep-001",
        track=Track.JAPAN,
        outline="일본 연봉의 진실",
        chapters=["hook", "body", "outro"],
        fact_sheet=FactSheet(facts={"jp_avg_salary": 4580000}),
    )
    assert manifest.validate_scene_facts([make_scene()]) == []
    missing_scene = make_scene(narration="{{fact:unknown_key}}가 문제다", caption="")
    assert manifest.validate_scene_facts([missing_scene]) == ["scene 1: unknown_key"]


def test_fact_sheet_hash_changes_with_facts():
    # 규칙 5-3: 파생 에셋의 version_hash 바인딩 근거
    a = FactSheet(facts={"k": 1})
    b = FactSheet(facts={"k": 2})
    assert a.version_hash and a.version_hash != b.version_hash
    assert FactSheet(facts={"k": 1}).version_hash == a.version_hash


def test_bible_is_frozen():
    # 잠금 자산 — 런타임 변경 불가
    bible = load_bible(Track.JAPAN)
    with pytest.raises(ValidationError):
        bible.voice_id = "hacked"


@pytest.mark.parametrize("track", list(Track))
def test_all_five_bibles_load(track):
    bible = load_bible(track)
    assert isinstance(bible, Bible)
    assert bible.channel == track


def test_cast_card_rejects_still_reference():
    # 규칙 5-5: 작품 스틸 참조 금지
    with pytest.raises(ValidationError):
        CastCard(name="여주", appearance="드라마 스틸컷과 동일한 얼굴")
    CastCard(name="여주", appearance="검은 단발, 20대 후반, 회색 코트")  # 창작 외형은 통과


def test_card_defaults():
    card = Card(card_id="c1", track=Track.DRAMA, title="3화 떡밥 정리")
    assert card.state == "draft"
    assert card.owner is None and card.approved_by is None
