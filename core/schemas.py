"""core/schemas.py — 씬 JSON v1, 채널 바이블, 에피소드 매니페스트 (Pydantic).

CLAUDE.md 4장의 핵심 데이터 모델 3종 + 소재 카드.
5장 절대 규칙이 각 모델에 어떻게 반영됐는지 해당 필드 주석에 명시한다.
"""

from __future__ import annotations

import hashlib
import json
import re
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


# ---------------------------------------------------------------------------
# 공통 enum
# ---------------------------------------------------------------------------

class Track(str, Enum):
    """카테고리별 에이전트 5개 (CLAUDE.md 1장)."""

    JAPAN = "japan"            # 일본 머니
    REALESTATE = "realestate"  # 부동산
    DRAMA = "drama"            # 드라마썰
    NATEPAN = "natepan"        # 사연
    PLAYLIST = "playlist"      # 플레이리스트 (60분 롱폼)


class VisualType(str, Enum):
    SLIDE = "slide"
    CHART = "chart"                  # 규칙 5-3: 차트는 fact_sheet version_hash에 바인딩되는 파생 에셋
    DOC_HIGHLIGHT = "doc_highlight"
    ILLUST = "illust"
    CLIP = "clip"                    # 규칙 5-5: 라이선스 메타 없는 클립은 ingest 거부
    LOOP_ART = "loop_art"


class VisualEffect(str, Enum):
    KENBURNS = "kenburns"
    ZOOM_CALLOUT = "zoom_callout"
    NONE = "none"


# ---------------------------------------------------------------------------
# 씬 JSON v1 — 전 트랙 공용
# ---------------------------------------------------------------------------

# 규칙 5-3(사실 시트 단일 출처): 수치는 내레이션/자막에 직접 쓰지 않고
# "{{fact:key}}" 토큰으로 fact_sheet를 참조한다. 렌더 직전에 치환된다.
FACT_REF_PATTERN = re.compile(r"\{\{fact:([a-zA-Z0-9_.\-]+)\}\}")


class SceneVisual(BaseModel):
    type: VisualType
    ref: str = Field(description="에셋 경로 또는 수동 대기열 프롬프트 ID")
    effect: VisualEffect = VisualEffect.NONE


class SceneContext(BaseModel):
    """규칙 5-2(부분 재생성): 씬 단위 재생성 시 억양·문맥 연결을 위해
    앞 씬 꼬리/뒷 씬 머리 문장을 프롬프트에 자동 주입한다."""

    prev_tail: str = ""
    next_head: str = ""


class Scene(BaseModel):
    """씬 JSON v1. 부분 재생성(규칙 5-2)의 최소 단위.

    - 오디오는 씬 레이어(내레이션·효과음, -14 LUFS)만 소유한다.
      BGM은 에피소드 글로벌 트랙이므로 씬 모델에는 BGM 필드가 없다(규칙 5-1).
    - duration은 tts.py가 ffprobe 실측 후 기입한다(생성 시점에는 None).
    """

    scene_id: int
    track: Track
    chapter: str
    narration: str
    caption: str
    visual: SceneVisual
    duration: float | None = Field(
        default=None, ge=0.0, description="tts.py가 ffprobe로 실측 후 기입 (초)"
    )
    context: SceneContext = Field(default_factory=SceneContext)

    def fact_refs(self) -> list[str]:
        """내레이션·자막이 참조하는 fact_sheet 키 목록 (규칙 5-3).

        qc.py가 이 키들이 매니페스트 fact_sheet에 존재하는지 검사한다.
        """
        return FACT_REF_PATTERN.findall(self.narration) + FACT_REF_PATTERN.findall(
            self.caption
        )


# ---------------------------------------------------------------------------
# 채널 바이블 — 채널당 1개, 잠금 자산 (data/bibles/{channel}.yaml)
# ---------------------------------------------------------------------------

class VoiceParams(BaseModel):
    stability: float = Field(ge=0.0, le=1.0)
    similarity: float = Field(ge=0.0, le=1.0)
    speed: float = Field(gt=0.0)


class Bible(BaseModel):
    """채널 바이블. frozen=True — 런타임에서 절대 변경 금지(잠금 자산).

    규칙 5-2(부분 재생성): 씬 재생성 시 이 잠금 자산(voice, style_anchors,
    subtitle_tokens, lut, character_refs)이 자동 주입되어 톤 일관성을 보장한다.
    규칙 5-5(저작권): banned_phrases에 트랙별 금지어(배우 실명 등)를 담고
    qc.py가 대본·프롬프트를 검사한다.
    """

    model_config = ConfigDict(frozen=True)

    channel: Track
    voice_id: str
    voice_params: VoiceParams
    style_anchors: tuple[str, ...] = Field(
        default=(), description="스타일 앵커 이미지 경로 (data/assets/ 하위)"
    )
    subtitle_tokens: dict[str, str] = Field(
        default_factory=dict, description="자막 폰트·크기·색 등 번인 토큰"
    )
    lut: str = ""
    bgm_set: tuple[str, ...] = Field(
        default=(),
        description="에피소드 글로벌 BGM 트랙 후보 (규칙 5-1: 씬 오디오에 굽지 않음)",
    )
    character_refs: tuple[str, ...] = ()
    glossary: dict[str, str] = Field(
        default_factory=dict, description="용어집 — qc.py가 표기 일관성 검사"
    )
    banned_phrases: tuple[str, ...] = Field(
        default=(), description="금지어 — qc.py 검사 대상 (규칙 5-5 포함)"
    )


# ---------------------------------------------------------------------------
# 에피소드 매니페스트 — 영상당 1개
# ---------------------------------------------------------------------------

class FactSheet(BaseModel):
    """수치의 단일 출처 (규칙 5-3).

    - 씬은 수치를 하드코딩하지 않고 {{fact:key}}로 이 시트를 참조한다.
    - 파생 에셋(차트)은 version_hash에 바인딩된다. facts가 바뀌면 해시가
      달라지고, qc.py가 해시 불일치 에셋에 자동 재렌더 플래그를 세운다.
    """

    version_hash: str = ""
    facts: dict[str, str | int | float] = Field(default_factory=dict)

    @staticmethod
    def compute_hash(facts: dict[str, str | int | float]) -> str:
        canonical = json.dumps(facts, ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]

    @model_validator(mode="after")
    def _fill_hash(self) -> "FactSheet":
        if not self.version_hash:
            object.__setattr__(self, "version_hash", self.compute_hash(self.facts))
        return self


class CastCard(BaseModel):
    """드라마썰 인물 외형 잠금 (규칙 5-2·5-5).

    일러스트 배치 생성 시 인물 카드를 프롬프트에 주입해 외형 일관성을 지키고,
    배우 실명·작품 스틸 참조 없이 창작 외형만 기술한다.
    """

    name: str
    appearance: str

    @field_validator("appearance")
    @classmethod
    def _no_still_reference(cls, v: str) -> str:
        # 규칙 5-5: 재연 컷 프롬프트에 작품 스틸 참조 금지 — 명시적 스틸 지시어 차단.
        lowered = v.lower()
        for banned in ("스틸컷", "스틸 컷", "official still", "screencap"):
            if banned in lowered:
                raise ValueError(f"인물 외형에 작품 스틸 참조 금지: {banned!r}")
        return v


class Manifest(BaseModel):
    """에피소드 매니페스트 — 영상당 1개."""

    episode_id: str
    track: Track
    outline: str
    chapters: list[str] = Field(default_factory=list)
    fact_sheet: FactSheet = Field(default_factory=FactSheet)
    cast_cards: list[CastCard] = Field(default_factory=list)

    def validate_scene_facts(self, scenes: list[Scene]) -> list[str]:
        """씬들이 참조하는 fact 키 중 시트에 없는 키를 반환 (규칙 5-3).

        qc.py가 호출한다. 반환값이 비어 있지 않으면 QC 실패.
        """
        missing: list[str] = []
        for scene in scenes:
            for key in scene.fact_refs():
                if key not in self.fact_sheet.facts:
                    missing.append(f"scene {scene.scene_id}: {key}")
        return missing


def load_bible(track: Track | str, bibles_dir: str = "data/bibles") -> Bible:
    """data/bibles/{track}.yaml을 읽어 검증된 Bible을 반환한다.

    잠금 자산이므로 반환 모델은 frozen — 호출부에서 수정 불가.
    """
    import pathlib

    import yaml

    track_value = track.value if isinstance(track, Track) else track
    path = pathlib.Path(bibles_dir) / f"{track_value}.yaml"
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    return Bible.model_validate(raw)


# ---------------------------------------------------------------------------
# 소재 카드 (scout.py 산출물, 상태머신의 대상)
# ---------------------------------------------------------------------------

class Card(BaseModel):
    """소재 카드. CLAUDE.md 4장: owner(맡은 사람, 잠금), approved_by(소재 확정자).

    - 규칙 5-4(클레임 잠금): owner가 있는 카드는 타인이 상태 전환 불가
      → statemachine.transition()이 강제한다.
    - 규칙 5-4(셀프 검수 금지): 리뷰 승인 시 승인자 == owner면 403
      → statemachine.approve_review()가 강제한다.
    """

    card_id: str
    track: Track
    title: str
    summary: str = ""
    source_ref: str = Field(default="", description="아웃라이어 원본 영상 등 출처")
    owner: str | None = Field(default=None, description="맡은 사람 (UI: '내가 맡기')")
    approved_by: str | None = Field(default=None, description="소재 확정자 (UI: '소재 확정')")
    state: str = "draft"
