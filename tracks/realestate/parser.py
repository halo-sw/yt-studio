"""부동산 — 반자동 파서: 후보 추출 → UI 클릭 확정.

Daum_Public_Housing 프로젝트의 공개 데이터(서울시 청년안심주택 등)에서
에피소드 후보 단지를 추출해 소재 카드로 만든다. 확정은 사람 게이트 1(소재 확정).

추출된 수치는 씬에 직접 쓰지 않고 fact_sheet에 적재한다 (규칙 5-3).
"""

from __future__ import annotations

import json
import os
import pathlib
import re
import urllib.parse
import urllib.request
import uuid

from pydantic import BaseModel

from core.schemas import Card, FactSheet, Track

# 데이터 소스: Daum_Public_Housing 프로젝트의 lib/ (환경변수로 재지정 가능)
DEFAULT_DATA_DIR = os.environ.get(
    "REALESTATE_DATA_DIR",
    os.path.expanduser("~/dev/Projects/Daum_Public_Housing/code/lib"),
)

_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
_YT_ID = r"[A-Za-z0-9_-]{11}"
_YT_PATTERN = re.compile(
    rf"(?:youtube\.com/(?:embed/|watch\?v=)|youtu\.be/)({_YT_ID})", re.I
)
_DIST_PATTERN = re.compile(r"(\d+)\s*m")


class OfficialVideo(BaseModel):
    """단지 공식 홈페이지에 임베드된 유튜브 영상 (투어/홍보)."""

    video_id: str
    title: str = ""
    relevant: bool = False  # 제목이 단지와 관련 있는지 (무관 임베드 걸러내기)


class Candidate(BaseModel):
    """에피소드 후보 단지. 수치 필드는 fact_sheet 적재용 원본 (규칙 5-3)."""

    home_code: str
    name: str
    gu: str = ""
    address: str = ""
    subway: str = ""
    deposit_low_won: int | None = None
    rent_low_won: int | None = None
    total_units: int | None = None
    phone: str = ""
    homepage: str = ""
    lat: float | None = None
    lng: float | None = None
    photo_url: str = ""
    video: OfficialVideo | None = None
    score: float = 0.0

    def station_distance_m(self) -> int | None:
        """'5호선 화곡역 6번출구 211m' → 211. 파싱 실패 시 None."""
        m = _DIST_PATTERN.search(self.subway)
        return int(m.group(1)) if m else None


def load_complexes(data_dir: str | None = None) -> list[dict]:
    """청년안심주택 단지 목록.

    우선순위 — 어느 머신에서도 자체 완결되게:
    1) yt-studio 자체 캐시 (data/realestate/complexes.json — 커밋된 스냅샷 포함)
    2) 캐시가 없으면 포털에서 즉시 수집 (scraper.sync_complexes, 키 불필요)
    3) 수집 실패 시 REALESTATE_DATA_DIR(레거시 외부 폴더) 폴백
    data_dir 인자를 명시하면 그 폴더의 youth-complexes.json을 그대로 읽는다.
    """
    if data_dir:
        path = pathlib.Path(data_dir) / "youth-complexes.json"
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    from tracks.realestate import scraper

    cache = scraper.load_cache()
    if cache:
        return cache["complexes"]
    try:
        return scraper.sync_complexes()["complexes"]
    except scraper.SyncError:
        legacy = pathlib.Path(DEFAULT_DATA_DIR) / "youth-complexes.json"
        if legacy.exists():
            with open(legacy, encoding="utf-8") as f:
                return json.load(f)
        raise


def _fetch(url: str, timeout: float = 12.0) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def _name_tokens(name: str) -> list[str]:
    """단지명에서 매칭용 토큰. '~역' 접두는 흔해서 제외한다."""
    return [t for t in re.split(r"\s+", name) if len(t) >= 2 and not t.endswith("역")]


def find_official_video(candidate: Candidate, timeout: float = 12.0) -> OfficialVideo | None:
    """공식 홈페이지에서 유튜브 임베드를 찾고 oEmbed 제목으로 관련성을 판정한다.

    무관 임베드(예: 예능 클립)를 거르기 위해 제목에 단지명 토큰 또는
    '청년안심주택/둘러보기/투어' 키워드가 있어야 relevant=True.
    """
    hp = candidate.homepage.strip()
    if not hp:
        return None
    if not hp.startswith("http"):
        hp = "https://" + hp
    try:
        html = _fetch(hp, timeout)
    except Exception:
        return None
    m = _YT_PATTERN.search(html)
    if not m:
        return None
    video_id = m.group(1)
    title = ""
    try:
        oembed = _fetch(
            "https://www.youtube.com/oembed?format=json&url="
            + urllib.parse.quote(f"https://www.youtube.com/watch?v={video_id}", safe=""),
            timeout,
        )
        title = json.loads(oembed).get("title", "")
    except Exception:
        pass
    keywords = _name_tokens(candidate.name) + ["청년안심주택", "둘러보기", "투어"]
    relevant = any(k in title for k in keywords)
    return OfficialVideo(video_id=video_id, title=title, relevant=relevant)


def _score(c: Candidate) -> float:
    """에피소드 제작 가치 점수. 에셋 확보 가능성과 스토리 소재 중심."""
    s = 0.0
    if c.lat and c.lng:
        s += 2.0  # 로드뷰·지도 캡처 가능
    if c.photo_url:
        s += 1.0
    if c.deposit_low_won and c.rent_low_won:
        s += 2.0  # 비용 계산 챕터 가능
    dist = c.station_distance_m()
    if dist is not None:
        s += 1.0
        if dist <= 300:
            s += 1.0  # 초역세권 훅
    if c.total_units and c.total_units >= 300:
        s += 0.5  # 대단지 = 모집 규모 소재
    if c.video and c.video.relevant:
        s += 3.0  # 내부 투어 비주얼 확보 — 최고 가점
    return s


def extract_candidates(
    complexes: list[dict],
    top_n: int = 10,
    check_videos: bool = False,
) -> list[Candidate]:
    """단지 목록 → 점수순 후보. check_videos=True면 홈페이지 영상도 조회(네트워크)."""
    out: list[Candidate] = []
    for c in complexes:
        cand = Candidate(
            home_code=str(c.get("homeCode", "")),
            name=c.get("homeName", ""),
            gu=c.get("gu", ""),
            address=c.get("address", ""),
            subway=c.get("subway", ""),
            deposit_low_won=c.get("depositLowWon"),
            rent_low_won=c.get("rentLowWon"),
            total_units=c.get("totalUnits"),
            phone=c.get("phone", ""),
            homepage=c.get("homepage", "") or "",
            lat=c.get("lat"),
            lng=c.get("lng"),
            photo_url=c.get("photoUrl", "") or "",
        )
        if check_videos and cand.homepage:
            cand.video = find_official_video(cand)
        cand.score = _score(cand)
        out.append(cand)
    out.sort(key=lambda x: x.score, reverse=True)
    return out[:top_n]


def make_cards(candidates: list[Candidate]) -> list[Card]:
    """후보 → 소재 카드. owner/approved_by 없음 — 확정은 사람 게이트 1."""
    cards = []
    for c in candidates:
        dist = c.station_distance_m()
        bits = [c.gu or c.address]
        if dist is not None:
            bits.append(f"역까지 {dist}m")
        if c.total_units:
            bits.append(f"{c.total_units}세대")
        if c.rent_low_won:
            bits.append(f"월세 {c.rent_low_won // 10000}만원~")
        if c.video and c.video.relevant:
            bits.append("공식 투어 영상 있음")
        cards.append(Card(
            card_id=str(uuid.uuid4()),
            track=Track.REALESTATE,
            title=c.name,
            summary=" · ".join(bits) + f" · 점수 {c.score:.1f}",
            source_ref=c.homepage
            or f"https://soco.seoul.go.kr/youth/pgm/home/yohome/view.do?menuNo=400002&homeCode={c.home_code}",
        ))
    return cards


def build_fact_sheet(c: Candidate) -> FactSheet:
    """후보의 수치를 fact_sheet에 적재 (규칙 5-3 — 씬은 {{fact:key}}로만 참조)."""
    facts: dict[str, str | int | float] = {
        "complex_name": c.name,
        "address": c.address,
        "subway_desc": c.subway,
    }
    if c.deposit_low_won is not None:
        facts["deposit_low_won"] = c.deposit_low_won
    if c.rent_low_won is not None:
        facts["rent_low_won"] = c.rent_low_won
    if c.total_units is not None:
        facts["total_units"] = c.total_units
    dist = c.station_distance_m()
    if dist is not None:
        facts["station_distance_m"] = dist
    if c.phone:
        facts["contact_phone"] = c.phone
    return FactSheet(facts=facts)
