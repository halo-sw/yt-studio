"""이라스토야(いらすとや) 소재 수집 유틸.

라이선스 (2026-07-25 terms.html 확인): 상업 이용 무료·크레딧 불요.
단, **하나의 제작물(영상 1편)에 21점 이상 사용 시 유료** → 편당 20점 한도를
코드로 강제한다. 다운로드 소재는 라이브러리에 캐시해 여러 편에 재사용.
"""
from __future__ import annotations

import re
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LIB = ROOT / "data/assets/psychology/irasutoya"
FREE_LIMIT_PER_VIDEO = 20

_UA = {"User-Agent": "Mozilla/5.0 (channel-factory asset fetcher)"}


def _get(url: str) -> str:
    req = urllib.request.Request(url, headers=_UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "ignore")


def _download(url: str, out: Path) -> Path:
    req = urllib.request.Request(url, headers=_UA)
    out.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(req, timeout=60) as r:
        out.write_bytes(r.read())
    return out


def search_feed(keyword: str, limit: int = 6) -> list[dict]:
    """Blogger 피드 검색 — 사이트 HTML은 JS 렌더링이라 피드 API가 정석.

    반환: [{title, url, thumb}] (thumb는 s72-c 썸네일 — s800으로 치환해 원본급)
    """
    import json
    q = urllib.parse.quote(keyword)
    raw = _get(f"https://www.irasutoya.com/feeds/posts/default?q={q}&alt=json&max-results={limit}")
    feed = json.loads(raw).get("feed", {})
    out = []
    for e in feed.get("entry", []):
        links = [l["href"] for l in e.get("link", []) if l.get("rel") == "alternate"]
        thumb = e.get("media$thumbnail", {}).get("url", "")
        if links and thumb:
            out.append({"title": e["title"]["$t"], "url": links[0], "thumb": thumb})
    return out


# 사이트 UI 이미지 (본문 일러스트가 아님) — 폴백 스캔에서 제외
_CHROME = ("menu", "logo", "button", "navigation", "pyoko", "search_",
           "apple-touch", "background", "twitter_card", "default", "banner")


def post_image_url(post_url: str) -> str | None:
    """포스트 본문의 원본 이미지 URL (s800 크기로 정규화)."""
    html = _get(post_url)
    m = (re.search(r'property=["\']og:image["\'][^>]*content=["\'](https://[^"\'\s]+)', html)
         or re.search(r'content=["\'](https://[^"\'\s]+)["\'][^>]*property=["\']og:image', html))
    if m:
        url = m.group(1)
    else:
        cands = re.findall(
            r'https://(?:blogger\.googleusercontent\.com|\d\.bp\.blogspot\.com)/[^\s"\'\\()<>]+?\.png',
            html)
        cands = [c for c in cands if not any(k in c.lower() for k in _CHROME)]
        if not cands:
            return None
        url = cands[0]
    return re.sub(r"/s\d+(-c)?/", "/s800/", url)


def _post_title(html: str) -> str:
    m = re.search(r"<title>([^<]+)</title>", html)
    return m.group(1) if m else ""


def _entry_image(html: str) -> str | None:
    """본문(entry) 영역의 첫 일러스트 PNG — og:image는 크롭이라 후순위."""
    body = html
    m = re.search(r'class=["\']entry["\']', html)
    if m:
        body = html[m.start():m.start() + 20000]
    cands = re.findall(
        r'https://(?:blogger\.googleusercontent\.com|\d\.bp\.blogspot\.com)/[^\s"\'\\()<>]+?\.png',
        body)
    cands = [c for c in cands if not any(k in c.lower() for k in _CHROME)]
    return cands[0] if cands else None


def fetch(keyword: str, slug: str, prefer: str = "") -> Path | None:
    """피드 검색 → 제목이 가장 잘 맞는 포스트의 일러스트를 라이브러리에 캐시.

    일본어 검색은 공백을 넣으면 결과가 0이 되므로 keyword는 단일 토큰이 안전하다.
    같은 키워드에 후보가 여럿일 때 `prefer`(제목에 포함될 문자열)로 원하는 컷을
    지정한다. 예: fetch("体育座り", "hitori", prefer="後ろ姿")
    """
    out = LIB / f"{slug}.png"
    if out.exists():
        return out
    tokens = keyword.split()
    entries = search_feed(keyword, limit=12 if prefer else 6)
    if not entries:
        print(f"   irasutoya {slug}: 검색 결과 없음 ({keyword})", flush=True)
        return None
    scored = sorted(entries, key=lambda e: (
        -(2 if prefer and prefer in e["title"] else 0)
        - sum(1 for t in tokens if t in e["title"])))
    best = scored[0]
    url = re.sub(r"/s\d+(-c)?/", "/s800/", best["thumb"])
    _download(url, out)
    print(f"   irasutoya {slug}: {best['title'][:36]}", flush=True)
    return out
