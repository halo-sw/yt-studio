"""M0 검증 — SQLAlchemy 스키마가 SQLite(v0)에서 생성·CRUD 되는지 확인.

스키마는 PostgreSQL과 동일 (CLAUDE.md 2장 — 공용 JSON 타입만 사용).
"""

from core.models import (
    AuditLogModel,
    CardModel,
    EpisodeModel,
    SceneModel,
    UsageLogModel,
    create_all,
    get_engine,
    get_sessionmaker,
)


def test_schema_roundtrip(tmp_path):
    engine = get_engine(f"sqlite:///{tmp_path}/test.db")
    create_all(engine)
    Session = get_sessionmaker(engine)

    with Session() as s:
        s.add(CardModel(card_id="c1", track="japan", title="테스트", owner="A", approved_by="B"))
        s.add(
            EpisodeModel(
                episode_id="ep1",
                card_id="c1",
                track="japan",
                fact_sheet={"jp_avg_salary": 4580000},
                fact_sheet_hash="abc123",
            )
        )
        s.add(
            SceneModel(
                episode_id="ep1",
                scene_id=1,
                track="japan",
                narration="{{fact:jp_avg_salary}}엔",
                visual={"type": "chart", "ref": "x.png", "effect": "none"},
            )
        )
        s.add(
            AuditLogModel(card_id="c1", actor="A", from_state="draft", to_state="scripted")
        )
        # 규칙 5-8: 재생성 크레딧 별도 집계
        s.add(UsageLogModel(service="elevenlabs", episode_id="ep1", units=120, is_regen=True))
        s.commit()

    with Session() as s:
        ep = s.get(EpisodeModel, "ep1")
        assert ep.card.owner == "A"
        assert ep.scenes[0].duration is None  # tts 실측 전
        assert ep.publish_verified is False  # 규칙 5-6: verify 전 기본값
        regen = s.query(UsageLogModel).filter_by(is_regen=True).all()
        assert len(regen) == 1
