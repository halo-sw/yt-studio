"""tracks/realestate/parser.py 단위 테스트 — 네트워크 없이 픽스처로."""

from core.schemas import Track
from tracks.realestate.parser import (
    Candidate,
    OfficialVideo,
    build_fact_sheet,
    extract_candidates,
    make_cards,
)

FIXTURE = [
    {  # 풀 데이터 + 초역세권 → 최고점
        "homeCode": "20000412", "homeName": "화곡역 포르투나 블루",
        "gu": "강서구", "address": "강서구 화곡로 146",
        "subway": "5호선 화곡역 6번출구 211m",
        "depositLowWon": 50_000_000, "rentLowWon": 80_000, "totalUnits": 82,
        "phone": "010-0000-0000", "homepage": "https://example.com",
        "lat": 37.54, "lng": 126.83, "photoUrl": "https://example.com/p.jpg",
    },
    {  # 좌표·사진 없음 → 저점
        "homeCode": "20000001", "homeName": "어딘가 하우스",
        "gu": "어느구", "address": "어느구 어느로 1", "subway": "",
        "depositLowWon": None, "rentLowWon": None, "totalUnits": 10,
        "phone": "", "homepage": "", "lat": None, "lng": None, "photoUrl": "",
    },
    {  # 대단지, 역거리 파싱 가능
        "homeCode": "20000597", "homeName": "화랑대역 에이트플레이스",
        "gu": "중랑구", "address": "중랑구 신내로 267",
        "subway": "6호선 화랑대역 6번출구 146m, 도보 2분",
        "depositLowWon": 48_000_000, "rentLowWon": 160_000, "totalUnits": 724,
        "phone": "02-0000-0000", "homepage": "https://example.org",
        "lat": 37.61, "lng": 127.08, "photoUrl": "https://example.org/p.jpg",
    },
]


def test_extract_candidates_scores_and_sorts():
    cands = extract_candidates(FIXTURE, top_n=3)
    assert [c.home_code for c in cands][:2] == ["20000597", "20000412"] or \
           [c.home_code for c in cands][:2] == ["20000412", "20000597"]
    assert cands[-1].home_code == "20000001"
    assert cands[0].score > cands[-1].score


def test_station_distance_parsing():
    c = Candidate(home_code="x", name="테스트", subway="5호선 화곡역 6번출구 211m")
    assert c.station_distance_m() == 211
    assert Candidate(home_code="y", name="테스트").station_distance_m() is None


def test_relevant_video_adds_top_bonus():
    base = extract_candidates(FIXTURE, top_n=3)
    scored = {c.home_code: c.score for c in base}
    with_video = [dict(f) for f in FIXTURE]
    cands = extract_candidates(with_video, top_n=3)
    target = next(c for c in cands if c.home_code == "20000412")
    target.video = OfficialVideo(video_id="r2-3qZQhbOE", title="포르투나 블루 둘러보기", relevant=True)
    from tracks.realestate.parser import _score
    assert _score(target) == scored["20000412"] + 3.0


def test_make_cards_summary_and_source():
    cands = extract_candidates(FIXTURE, top_n=3)
    cards = make_cards(cands)
    assert all(card.track == Track.REALESTATE for card in cards)
    fortuna = next(c for c in cards if "포르투나" in c.title)
    assert "역까지 211m" in fortuna.summary
    assert "월세 8만원~" in fortuna.summary
    assert fortuna.source_ref.startswith("https://")
    # 홈페이지 없는 후보는 서울시 포털 링크로 폴백
    fallback = next(c for c in cards if "어딘가" in c.title)
    assert "soco.seoul.go.kr" in fallback.source_ref


def test_fact_sheet_holds_numbers_not_scenes():
    """규칙 5-3: 수치는 fact_sheet가 단일 출처. 키 존재와 해시 생성 검증."""
    cand = extract_candidates(FIXTURE, top_n=1)[0]
    fs = build_fact_sheet(cand)
    assert fs.facts["deposit_low_won"] in (50_000_000, 48_000_000)
    assert "station_distance_m" in fs.facts
    assert fs.version_hash  # facts 변경 시 파생 에셋 재렌더 플래그의 기준
