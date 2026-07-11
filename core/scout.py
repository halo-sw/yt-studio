"""core/scout.py — 경쟁사 분석: 경쟁 채널 폴링(YouTube API) → 아웃라이어 감지 → 소재 카드.

산출물은 core.schemas.Card (state=draft, owner/approved_by 없음) + 채널별
CompetitorReport. 사람 게이트 1(소재 확정) 전에는 파이프라인이 진행되지
않는다 (statemachine이 강제).

아웃라이어 정의: 같은 채널의 최근 영상 중앙값 조회수 대비 배수(multiple)가
임계(기본 3.0×) 이상이면서 최근성 가중치를 곱한 점수가 높은 영상.
중앙값을 쓰는 이유 — 바이럴 1건이 평균을 끌어올려 후속 아웃라이어를
가리는 것을 막기 위해서다.

YOUTUBE_API_KEY가 없으면 픽스처 데이터로 폴백해 e2e 테스트가 가능하다.
harvest.py의 지표 피드백(M4)은 여기의 score 가중치를 조정한다.
"""

from __future__ import annotations

import os
import statistics
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from core.schemas import Card, Track

# ---------------------------------------------------------------------------
# 데이터 모델
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class VideoStat:
    video_id: str
    channel_id: str
    channel_name: str
    title: str
    views: int
    published_at: datetime
    duration_s: int = 0


@dataclass(frozen=True)
class Outlier:
    video: VideoStat
    multiple: float        # 채널 중앙값 대비 배수
    recency_weight: float  # 0~1 (14일 선형 감쇠)
    score: float           # multiple × recency — 소재 카드 정렬 기준


@dataclass
class CompetitorReport:
    """채널 1개의 분석 요약 — UI '자세히' 패널의 경쟁사 분석 블록 데이터."""

    channel_id: str
    channel_name: str
    video_count: int
    median_views: int
    mean_views: int
    uploads_per_week: float
    outliers: list[Outlier] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "channel": self.channel_name,
            "videos": self.video_count,
            "median_views": self.median_views,
            "mean_views": self.mean_views,
            "uploads_per_week": round(self.uploads_per_week, 1),
            "outliers": [
                {"title": o.video.title, "views": o.video.views,
                 "multiple": round(o.multiple, 1), "score": round(o.score, 1)}
                for o in self.outliers
            ],
        }


# ---------------------------------------------------------------------------
# 아웃라이어 감지
# ---------------------------------------------------------------------------

RECENCY_WINDOW_DAYS = 14
DEFAULT_MIN_MULTIPLE = 3.0


def recency_weight(published_at: datetime, now: datetime | None = None) -> float:
    """0~1 선형 감쇠 — 14일 지난 영상은 소재 가치 0으로 본다."""
    now = now or datetime.now(timezone.utc)
    age_days = (now - published_at).total_seconds() / 86_400
    return max(0.0, 1.0 - age_days / RECENCY_WINDOW_DAYS)


def analyze_channel(
    videos: list[VideoStat], min_multiple: float = DEFAULT_MIN_MULTIPLE,
    now: datetime | None = None,
) -> CompetitorReport:
    """채널 1개의 최근 영상 목록 → 기준선 + 아웃라이어."""
    if not videos:
        raise ValueError("영상 목록이 비어 있음")
    views = [v.views for v in videos]
    median = int(statistics.median(views))
    first, last = min(v.published_at for v in videos), max(v.published_at for v in videos)
    weeks = max((last - first).total_seconds() / (7 * 86_400), 1 / 7)
    outliers = []
    for v in videos:
        multiple = v.views / max(median, 1)
        rw = recency_weight(v.published_at, now)
        if multiple >= min_multiple and rw > 0:
            outliers.append(Outlier(video=v, multiple=multiple, recency_weight=rw,
                                    score=round(multiple * rw, 2)))
    outliers.sort(key=lambda o: o.score, reverse=True)
    return CompetitorReport(
        channel_id=videos[0].channel_id, channel_name=videos[0].channel_name,
        video_count=len(videos), median_views=median,
        mean_views=int(statistics.mean(views)),
        uploads_per_week=len(videos) / weeks, outliers=outliers,
    )


def make_cards(track: Track, reports: list[CompetitorReport], top_n: int = 5) -> list[Card]:
    """아웃라이어 → 소재 카드. owner/approved_by 없음 — 확정은 사람 게이트 1."""
    pool = [(o, r) for r in reports for o in r.outliers]
    pool.sort(key=lambda x: x[0].score, reverse=True)
    cards = []
    for o, r in pool[:top_n]:
        cards.append(Card(
            card_id=str(uuid.uuid4()), track=track, title=o.video.title,
            summary=(
                f"아웃라이어 점수 {o.score} · 채널 중앙값의 {o.multiple:.1f}배 "
                f"({o.video.views:,}회 vs 중앙값 {r.median_views:,}회) · "
                f"{r.channel_name}, 주 {r.uploads_per_week:.1f}회 업로드"
            ),
            source_ref=f"https://youtu.be/{o.video.video_id}",
        ))
    return cards


# ---------------------------------------------------------------------------
# 폴링 (YouTube Data API, 키 없으면 픽스처 폴백)
# ---------------------------------------------------------------------------

def poll_competitors(
    channel_ids: list[str], api_key: str | None = None, max_videos: int = 15,
) -> list[list[VideoStat]]:
    """채널별 최근 영상 통계. service/workers의 poll_competitors 잡이 호출."""
    key = api_key or os.getenv("YOUTUBE_API_KEY")
    if not key:
        return [_fixture_channel(cid) for cid in channel_ids]

    from googleapiclient.discovery import build

    yt = build("youtube", "v3", developerKey=key)
    result = []
    for cid in channel_ids:
        search = yt.search().list(channelId=cid, part="id", order="date",
                                  maxResults=max_videos, type="video").execute()
        ids = [it["id"]["videoId"] for it in search.get("items", [])]
        stats = yt.videos().list(id=",".join(ids), part="snippet,statistics").execute()
        vids = [
            VideoStat(
                video_id=it["id"], channel_id=cid,
                channel_name=it["snippet"]["channelTitle"], title=it["snippet"]["title"],
                views=int(it["statistics"].get("viewCount", 0)),
                published_at=datetime.fromisoformat(
                    it["snippet"]["publishedAt"].replace("Z", "+00:00")),
            )
            for it in stats.get("items", [])
        ]
        result.append(vids)
    return result


def _fixture_channel(channel_id: str) -> list[VideoStat]:
    """API 키 없는 환경용 결정적 픽스처 — 중앙값 40k, 아웃라이어 2건 포함."""
    now = datetime.now(timezone.utc)
    base = [42_000, 38_000, 45_000, 39_000, 41_000, 37_000, 44_000, 40_000]
    vids = [
        VideoStat(video_id=f"{channel_id}-{i}", channel_id=channel_id,
                  channel_name=f"경쟁채널-{channel_id[-4:]}", title=f"평상시 영상 {i + 1}",
                  views=v, published_at=now - timedelta(days=20 + i))
        for i, v in enumerate(base)
    ]
    vids += [
        VideoStat(video_id=f"{channel_id}-hot1", channel_id=channel_id,
                  channel_name=f"경쟁채널-{channel_id[-4:]}",
                  title="시청률 역주행 드라마 3화, 왜 지금 터졌나",
                  views=168_000, published_at=now - timedelta(days=3)),
        VideoStat(video_id=f"{channel_id}-hot2", channel_id=channel_id,
                  channel_name=f"경쟁채널-{channel_id[-4:]}",
                  title="일본 20대 평균 연봉의 함정",
                  views=115_000, published_at=now - timedelta(days=5)),
    ]
    return vids


def scout(track: Track, channel_ids: list[str], api_key: str | None = None,
          min_multiple: float = DEFAULT_MIN_MULTIPLE) -> tuple[list[Card], list[CompetitorReport]]:
    """경쟁사 분석 진입점: 폴링 → 채널별 리포트 → 소재 카드 생성."""
    reports = [
        analyze_channel(videos, min_multiple=min_multiple)
        for videos in poll_competitors(channel_ids, api_key=api_key) if videos
    ]
    return make_cards(track, reports), reports
