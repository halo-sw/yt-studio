"""core/models.py — SQLAlchemy DB 모델.

PostgreSQL(Docker)이 기본, v0은 SQLite 허용 — 스키마는 동일하게 유지한다
(CLAUDE.md 2장). 그래서 DB 방언 특화 타입(JSONB 등) 대신 공용 JSON을 쓴다.

5장 절대 규칙 반영 위치:
- 규칙 5-3: EpisodeModel.fact_sheet(단일 출처) + AssetModel.fact_sheet_hash
  바인딩 → qc.py가 해시 불일치 시 needs_rerender 플래그를 세운다.
- 규칙 5-4: CardModel.owner / approved_by 컬럼. 강제는 core.statemachine이
  하고, 모든 전환은 AuditLogModel에 기록된다.
- 규칙 5-5: AssetModel.license_meta — NULL인 클립은 ingest 단계에서 거부.
- 규칙 5-6: EpisodeModel.publish_verified — publish 후 verify 결과 기록.
- 규칙 5-8: UsageLogModel.is_regen — 재생성 크레딧 별도 집계.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class CardModel(Base):
    """소재 카드 (schemas.Card의 영속화)."""

    __tablename__ = "cards"

    card_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    track: Mapped[str] = mapped_column(String(20), index=True)
    title: Mapped[str] = mapped_column(String(300))
    summary: Mapped[str] = mapped_column(Text, default="")
    source_ref: Mapped[str] = mapped_column(String(500), default="")
    # 규칙 5-4 클레임 잠금: owner가 있으면 타인이 상태 전환 불가 (statemachine이 강제).
    owner: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # 규칙 5-4 셀프 검수 금지: approved_by == 리뷰 승인 요청자면 API가 403.
    approved_by: Mapped[str | None] = mapped_column(String(50), nullable=True)
    state: Mapped[str] = mapped_column(String(20), default="draft", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    episodes: Mapped[list["EpisodeModel"]] = relationship(back_populates="card")


class EpisodeModel(Base):
    """에피소드 매니페스트 (schemas.Manifest의 영속화)."""

    __tablename__ = "episodes"

    episode_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    card_id: Mapped[str] = mapped_column(ForeignKey("cards.card_id"), index=True)
    track: Mapped[str] = mapped_column(String(20), index=True)
    outline: Mapped[str] = mapped_column(Text, default="")
    chapters: Mapped[list] = mapped_column(JSON, default=list)
    # 규칙 5-3 사실 시트 단일 출처: 수치는 여기에만 저장, 씬은 {{fact:key}}로 참조.
    fact_sheet: Mapped[dict] = mapped_column(JSON, default=dict)
    fact_sheet_hash: Mapped[str] = mapped_column(String(16), default="")
    # 규칙 5-5: 드라마썰 인물 외형 잠금 카드 (name, appearance).
    cast_cards: Mapped[list] = mapped_column(JSON, default=list)
    state: Mapped[str] = mapped_column(String(20), default="draft", index=True)
    scheduled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    youtube_video_id: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # 규칙 5-6: publish 후 상태 verify 필수 — verify 성공 시에만 True.
    publish_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    card: Mapped["CardModel"] = relationship(back_populates="episodes")
    scenes: Mapped[list["SceneModel"]] = relationship(
        back_populates="episode", order_by="SceneModel.scene_id"
    )
    assets: Mapped[list["AssetModel"]] = relationship(back_populates="episode")


class SceneModel(Base):
    """씬 JSON v1 (schemas.Scene의 영속화). 부분 재생성(규칙 5-2)의 최소 단위."""

    __tablename__ = "scenes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    episode_id: Mapped[str] = mapped_column(ForeignKey("episodes.episode_id"), index=True)
    scene_id: Mapped[int] = mapped_column(Integer)  # 에피소드 내 순번
    track: Mapped[str] = mapped_column(String(20))
    chapter: Mapped[str] = mapped_column(String(100), default="")
    narration: Mapped[str] = mapped_column(Text)
    caption: Mapped[str] = mapped_column(Text, default="")
    visual: Mapped[dict] = mapped_column(JSON, default=dict)  # {type, ref, effect}
    # tts.py가 ffprobe 실측 후 기입 (규칙 5-7 길이 제어의 근거 데이터).
    duration: Mapped[float | None] = mapped_column(Float, nullable=True)
    # 규칙 5-2: 부분 재생성 시 억양·문맥 연결용 컨텍스트.
    prev_tail: Mapped[str] = mapped_column(Text, default="")
    next_head: Mapped[str] = mapped_column(Text, default="")
    # 콘테 — 정보 포인트/감정(톤·낭독)/구도/시각 연출 (schemas.Conte 직렬화).
    conte: Mapped[dict] = mapped_column(JSON, default=dict)
    # 씬 레이어 오디오(내레이션·효과음, -14 LUFS) 경로.
    # BGM은 에피소드 글로벌 트랙이므로 씬에 컬럼이 없다 (규칙 5-1).
    audio_path: Mapped[str | None] = mapped_column(String(500), nullable=True)

    episode: Mapped["EpisodeModel"] = relationship(back_populates="scenes")


class AssetModel(Base):
    """비주얼/오디오 에셋 (차트, 일러스트, 클립, BGM 등)."""

    __tablename__ = "assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    episode_id: Mapped[str | None] = mapped_column(
        ForeignKey("episodes.episode_id"), nullable=True, index=True
    )
    kind: Mapped[str] = mapped_column(String(30))  # chart|illust|clip|bgm|loop_art|...
    path: Mapped[str] = mapped_column(String(500))
    # 규칙 5-3: 파생 에셋(차트)은 생성 시점의 fact_sheet 해시에 바인딩.
    # 에피소드의 fact_sheet_hash와 다르면 qc.py가 needs_rerender를 세운다.
    fact_sheet_hash: Mapped[str | None] = mapped_column(String(16), nullable=True)
    needs_rerender: Mapped[bool] = mapped_column(Boolean, default=False)
    # 규칙 5-5: 라이선스 메타 없는 클립은 ingest 거부 — clip은 NULL 저장 금지
    # (ingest 코드가 강제, 격리 계정 소재도 예외 없음).
    license_meta: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    episode: Mapped["EpisodeModel"] = relationship(back_populates="assets")


class AuditLogModel(Base):
    """감사 로그 — 모든 상태 전환·승인·클레임 기록 (CLAUDE.md 4장, UI '기록' 화면)."""

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    card_id: Mapped[str] = mapped_column(String(36), index=True)
    actor: Mapped[str] = mapped_column(String(50))
    from_state: Mapped[str] = mapped_column(String(20))
    to_state: Mapped[str] = mapped_column(String(20))
    note: Mapped[str] = mapped_column(Text, default="")
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class UsageLogModel(Base):
    """외부 API 사용량 (규칙 5-8 관제 임계).

    ElevenLabs 사용량 80% 경고의 근거 데이터. is_regen=True면 부분 재생성에
    쓴 크레딧 — 별도 집계해 UI '기록' 화면에 노출한다.
    """

    __tablename__ = "usage_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    service: Mapped[str] = mapped_column(String(30))  # elevenlabs|anthropic|youtube
    episode_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    units: Mapped[float] = mapped_column(Float)  # 크레딧/문자수/쿼터 등 서비스 단위
    is_regen: Mapped[bool] = mapped_column(Boolean, default=False)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class VoteModel(Base):
    """함께 결정 (2/3 투표) — UI 6장 추가 화면."""

    __tablename__ = "votes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    topic: Mapped[str] = mapped_column(String(300))
    card_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    voter: Mapped[str] = mapped_column(String(50))
    choice: Mapped[str] = mapped_column(String(50))
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


# ---------------------------------------------------------------------------
# 엔진/세션 헬퍼 — DATABASE_URL 미설정 시 v0 SQLite 폴백 (스키마 동일)
# ---------------------------------------------------------------------------

def get_engine(database_url: str | None = None):
    url = database_url or os.getenv("DATABASE_URL") or "sqlite:///data/channel_factory.db"
    return create_engine(url)


def create_all(engine) -> None:
    Base.metadata.create_all(engine)


def get_sessionmaker(engine) -> sessionmaker:
    return sessionmaker(bind=engine, expire_on_commit=False)
