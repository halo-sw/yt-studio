"""core/statemachine.py — 에피소드/카드 상태머신.

상태: draft → scripted → voiced → rendered → reviewed → scheduled → published
(CLAUDE.md 4장). 모든 전환은 audit_log에 기록된다.

5장 절대 규칙 반영:
- 규칙 5-4 클레임 잠금: owner가 있는 카드는 타인이 상태 전환 불가.
- 규칙 5-4 셀프 검수 금지: 리뷰 승인자 == owner(제작 요청자)면 거부
  → service/api의 리뷰 승인 라우터가 SelfReviewError를 403으로 매핑한다.
- 규칙 5-6 발행 하이브리드: published 진입은 publish.py의 verify 이후에만
  호출한다(여기서는 순서만 강제, verify 자체는 publish.py 책임).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from core.schemas import Card


class EpisodeState(str, Enum):
    DRAFT = "draft"
    SCRIPTED = "scripted"
    VOICED = "voiced"
    RENDERED = "rendered"
    REVIEWED = "reviewed"
    SCHEDULED = "scheduled"
    PUBLISHED = "published"


# 전진은 한 단계씩만. 후퇴는 부분 재생성(규칙 5-2)으로 인한 재작업 경로만 허용:
# 씬 대본 수정 → scripted, 씬 음성 재생성 → voiced, 씬 교체 렌더 → rendered.
# published에서의 후퇴는 없다(발행 철회는 별도 운영 절차).
_TRANSITIONS: dict[EpisodeState, set[EpisodeState]] = {
    EpisodeState.DRAFT: {EpisodeState.SCRIPTED},
    EpisodeState.SCRIPTED: {EpisodeState.VOICED},
    EpisodeState.VOICED: {EpisodeState.RENDERED, EpisodeState.SCRIPTED},
    EpisodeState.RENDERED: {EpisodeState.REVIEWED, EpisodeState.SCRIPTED, EpisodeState.VOICED},
    EpisodeState.REVIEWED: {EpisodeState.SCHEDULED, EpisodeState.RENDERED},
    EpisodeState.SCHEDULED: {EpisodeState.PUBLISHED, EpisodeState.REVIEWED},
    EpisodeState.PUBLISHED: set(),
}


class TransitionError(Exception):
    """허용되지 않은 상태 전환."""


class ClaimLockError(TransitionError):
    """규칙 5-4: owner가 있는 카드를 타인이 전환하려 함."""


class SelfReviewError(TransitionError):
    """규칙 5-4: 셀프 검수 시도 — API 레이어에서 403으로 매핑."""


class ApprovalRequiredError(TransitionError):
    """소재 확정(approved_by) 없이 draft를 벗어나려 함 — 사람 게이트 1."""


@dataclass(frozen=True)
class AuditEntry:
    """감사 로그 한 줄. 모든 전환은 audit_log에 기록 (CLAUDE.md 4장).

    core.models.AuditLog(DB 테이블)로 영속화된다.
    """

    card_id: str
    actor: str
    from_state: str
    to_state: str
    note: str = ""
    at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


def can_transition(current: EpisodeState, target: EpisodeState) -> bool:
    return target in _TRANSITIONS[current]


def transition(
    card: Card, target: EpisodeState, actor: str, note: str = ""
) -> AuditEntry:
    """카드 상태를 전환하고 감사 로그 엔트리를 반환한다.

    호출자는 반환된 AuditEntry를 반드시 DB(audit_log)에 저장해야 한다.
    """
    current = EpisodeState(card.state)

    if not can_transition(current, target):
        raise TransitionError(f"{current.value} → {target.value} 전환은 허용되지 않음")

    # 규칙 5-4 클레임 잠금: owner가 있는 카드는 타인이 상태 전환 불가.
    if card.owner is not None and actor != card.owner:
        raise ClaimLockError(
            f"카드 {card.card_id}는 {card.owner}가 맡은 카드 — {actor}는 전환 불가"
        )

    # 사람 게이트 1(소재 확정): 확정자 없이는 제작 파이프라인 진입 금지.
    if current is EpisodeState.DRAFT and card.approved_by is None:
        raise ApprovalRequiredError(f"카드 {card.card_id}: 소재 확정 전에는 대본 생성 불가")

    # 사람 게이트 2(최종 검토): reviewed 진입은 approve_review()로만.
    if target is EpisodeState.REVIEWED:
        raise TransitionError("reviewed 진입은 approve_review()를 통해서만 가능")

    card.state = target.value
    return AuditEntry(
        card_id=card.card_id,
        actor=actor,
        from_state=current.value,
        to_state=target.value,
        note=note,
    )


def approve_review(card: Card, reviewer: str, note: str = "") -> AuditEntry:
    """최종 검토 승인 (rendered → reviewed). 사람 게이트 2.

    규칙 5-4 셀프 검수 금지 — 두 검사 모두 위반 시 SelfReviewError,
    service/api 리뷰 라우터는 이를 HTTP 403으로 반환한다:
    1) 규칙 원문 그대로: approved_by(소재 확정자) == 승인 요청자면 403.
    2) 셀프 검수의 본질: 카드 owner(제작자)는 자기 결과물을 승인할 수 없다.
    셀프 승인 우회 로직 금지(CLAUDE.md 10장) — 이 검사를 건너뛰는 경로를 만들지 않는다.
    """
    current = EpisodeState(card.state)
    if current is not EpisodeState.RENDERED:
        raise TransitionError(f"리뷰 승인은 rendered 상태에서만 가능 (현재 {current.value})")

    if reviewer == card.approved_by:
        raise SelfReviewError(
            f"셀프 검수 금지: {reviewer}는 카드 {card.card_id}의 소재 확정자"
        )
    if reviewer == card.owner:
        raise SelfReviewError(
            f"셀프 검수 금지: {reviewer}는 카드 {card.card_id}의 owner"
        )

    card.state = EpisodeState.REVIEWED.value
    return AuditEntry(
        card_id=card.card_id,
        actor=reviewer,
        from_state=current.value,
        to_state=EpisodeState.REVIEWED.value,
        note=note or "최종 검토 승인",
    )


def claim(card: Card, actor: str) -> AuditEntry:
    """카드 맡기 (UI: '내가 맡기'). 이미 owner가 있으면 잠금 위반."""
    if card.owner is not None and card.owner != actor:
        raise ClaimLockError(f"카드 {card.card_id}는 이미 {card.owner}가 맡음")
    card.owner = actor
    return AuditEntry(
        card_id=card.card_id,
        actor=actor,
        from_state=card.state,
        to_state=card.state,
        note="카드 맡기",
    )


def approve_material(card: Card, approver: str) -> AuditEntry:
    """소재 확정 (UI: '소재 확정'). 사람 게이트 1 — draft 탈출의 전제 조건."""
    card.approved_by = approver
    return AuditEntry(
        card_id=card.card_id,
        actor=approver,
        from_state=card.state,
        to_state=card.state,
        note="소재 확정",
    )
