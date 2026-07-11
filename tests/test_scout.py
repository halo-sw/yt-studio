"""scout.py 검증 — 경쟁사 분석: 기준선, 아웃라이어, 소재 카드."""

from datetime import datetime, timedelta, timezone

from core.schemas import Track
from core.scout import (
    VideoStat,
    analyze_channel,
    make_cards,
    recency_weight,
    scout,
)

NOW = datetime(2026, 7, 11, 12, 0, tzinfo=timezone.utc)


def vid(i, views, days_ago, title=None):
    return VideoStat(video_id=f"v{i}", channel_id="ch1", channel_name="경쟁A",
                     title=title or f"영상 {i}", views=views,
                     published_at=NOW - timedelta(days=days_ago))


def test_outlier_uses_median_not_mean():
    # 바이럴 1건(300k)이 있어도 중앙값(40k) 기준이라 2번째 아웃라이어(130k)가 잡힌다
    videos = [vid(i, 40_000, 20 + i) for i in range(8)]
    videos += [vid(90, 300_000, 30), vid(91, 130_000, 2, "터진 소재")]
    report = analyze_channel(videos, now=NOW)
    assert report.median_views == 40_000
    titles = [o.video.title for o in report.outliers]
    assert "터진 소재" in titles


def test_recency_decay_suppresses_old_outliers():
    assert recency_weight(NOW - timedelta(days=1), NOW) > 0.9
    assert recency_weight(NOW - timedelta(days=20), NOW) == 0.0
    videos = [vid(i, 40_000, 20 + i) for i in range(8)] + [vid(9, 200_000, 30, "옛날 바이럴")]
    report = analyze_channel(videos, now=NOW)
    assert all(o.video.title != "옛날 바이럴" for o in report.outliers)


def test_make_cards_are_unclaimed_drafts():
    videos = [vid(i, 40_000, 15 + i) for i in range(8)] + [vid(9, 170_000, 3, "핫한 소재")]
    report = analyze_channel(videos, now=NOW)
    cards = make_cards(Track.DRAMA, [report])
    assert cards and cards[0].title == "핫한 소재"
    c = cards[0]
    # 사람 게이트 1 전: owner/approved_by 없음, draft 상태
    assert c.owner is None and c.approved_by is None and c.state == "draft"
    assert "배" in c.summary and c.source_ref.startswith("https://youtu.be/")


def test_scout_e2e_with_fixture():
    # YOUTUBE_API_KEY 없이 픽스처 폴백으로 e2e
    cards, reports = scout(Track.DRAMA, ["UCfixture01"], api_key=None)
    assert cards and reports
    assert reports[0].median_views > 0
    assert any("역주행" in c.title for c in cards)
