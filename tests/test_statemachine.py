"""M0 검증 — 상태머신: 전환 규칙, 클레임 잠금, 셀프 검수 금지, 감사 로그."""

import pytest

from core.schemas import Card, Track
from core.statemachine import (
    ApprovalRequiredError,
    ClaimLockError,
    EpisodeState,
    SelfReviewError,
    TransitionError,
    approve_material,
    approve_review,
    claim,
    transition,
)


def make_card(**overrides) -> Card:
    base = dict(card_id="c1", track=Track.JAPAN, title="테스트 소재")
    base.update(overrides)
    return Card(**base)


def test_draft_requires_material_approval():
    # 사람 게이트 1: 소재 확정 없이 대본 생성 불가
    card = make_card(owner="A")
    with pytest.raises(ApprovalRequiredError):
        transition(card, EpisodeState.SCRIPTED, actor="A")
    approve_material(card, approver="B")
    entry = transition(card, EpisodeState.SCRIPTED, actor="A")
    assert card.state == "scripted"
    assert (entry.from_state, entry.to_state) == ("draft", "scripted")


def test_claim_lock_blocks_others():
    # 규칙 5-4: owner가 있는 카드는 타인이 상태 전환 불가
    card = make_card(owner="A", approved_by="B", state="scripted")
    with pytest.raises(ClaimLockError):
        transition(card, EpisodeState.VOICED, actor="B")
    transition(card, EpisodeState.VOICED, actor="A")
    assert card.state == "voiced"


def test_claim_is_exclusive():
    card = make_card()
    claim(card, "A")
    assert card.owner == "A"
    with pytest.raises(ClaimLockError):
        claim(card, "B")


def test_no_skipping_states():
    card = make_card(owner="A", approved_by="B")
    with pytest.raises(TransitionError):
        transition(card, EpisodeState.RENDERED, actor="A")


def test_self_review_forbidden():
    # 규칙 5-4: 셀프 검수 금지 — owner도, 소재 확정자도 승인 불가 (API에선 403)
    card = make_card(owner="A", approved_by="B", state="rendered")
    with pytest.raises(SelfReviewError):
        approve_review(card, reviewer="A")  # owner
    with pytest.raises(SelfReviewError):
        approve_review(card, reviewer="B")  # 소재 확정자
    entry = approve_review(card, reviewer="C")  # 제3자만 가능
    assert card.state == "reviewed"
    assert entry.actor == "C"


def test_reviewed_only_via_approve_review():
    card = make_card(owner="A", approved_by="B", state="rendered")
    with pytest.raises(TransitionError):
        transition(card, EpisodeState.REVIEWED, actor="A")


def test_regen_rollback_paths():
    # 규칙 5-2: 부분 재생성으로 인한 후퇴 경로 (rendered → voiced 등)
    card = make_card(owner="A", approved_by="B", state="rendered")
    transition(card, EpisodeState.VOICED, actor="A", note="씬 7 음성 재생성")
    assert card.state == "voiced"


def test_published_is_terminal():
    card = make_card(owner="A", approved_by="B", state="published")
    with pytest.raises(TransitionError):
        transition(card, EpisodeState.SCHEDULED, actor="A")
