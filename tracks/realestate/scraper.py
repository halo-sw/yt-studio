"""부동산 — 매물 데이터 자체 수집기 (서울시 청년안심주택 포털).

외부 프로젝트 폴더에 의존하지 않는다. soco.seoul.go.kr의 공개 JSON 두 개를
직접 호출해 yt-studio 자체 캐시(data/realestate/complexes.json)를 만든다:

- yoHomeListJson.json : 카드 목록 (전 단지 — 가격·주소·역·사진, 키 불필요)
- maplist.json        : 지도 목록 (좌표·세대수·전화·홈페이지 서브셋) → homeCode 병합

UI의 "매물 새로 수집" 버튼과 cli `re-sync`가 호출한다.
"""

from __future__ import annotations

import json
import pathlib
import time
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[2]
CACHE_PATH = ROOT / "data" / "realestate" / "complexes.json"

_BASE = "https://soco.seoul.go.kr"
_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/126 Safari/537.36")


class SyncError(RuntimeError):
    pass


def _post_json(path: str, form: dict[str, str], timeout: float = 20.0) -> dict:
    body = urllib.parse.urlencode(form).encode()
    req = urllib.request.Request(
        _BASE + path, data=body,
        headers={"User-Agent": _UA,
                 "Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8", errors="ignore"))
    except Exception as e:  # noqa: BLE001 — 호출부에 명확한 안내로 변환
        raise SyncError(f"청년안심주택 포털 호출 실패 ({path}): {e}") from e


def sync_complexes(cache_path: pathlib.Path = CACHE_PATH) -> dict:
    """포털에서 단지 전체를 수집·병합해 캐시로 저장한다. 반환: 캐시 dict."""
    cards = _post_json(
        "/youth/pgm/home/yohome/yoHomeListJson.json",
        {"pageNum": "1", "rowCount": "300", "searchPresale": "", "searchTheme": "",
         "searchMovinHoman": "", "searchHouseType": "", "searchHouseForm": "",
         "searchAdresGu": "", "searchSil": ""},
    ).get("resultList") or []
    if not cards:
        raise SyncError("카드 목록이 비어 있음 — 포털 응답 형식이 바뀌었을 수 있음")

    map_rows = _post_json("/youth/pgm/home/yohome/maplist.json", {}).get(
        "mapResultList") or []
    by_code = {m.get("homeCode"): m for m in map_rows}

    complexes = []
    for c in cards:
        m = by_code.get(c.get("homeCode"), {})
        file_id = c.get("fileId")
        complexes.append({
            "homeCode": c.get("homeCode"),
            "homeName": c.get("homeName"),
            "gu": c.get("adresGu") or "",
            "address": f'{c.get("adresGu") or ""} {c.get("adresRo") or ""}'.strip(),
            "subway": c.get("optionSubway") or "",
            "depositLowWon": c.get("moneyDepositLow"),
            "rentLowWon": c.get("moneyRentalLow"),
            "totalUnits": int(m["scaleTot"]) if m.get("scaleTot") else None,
            "phone": m.get("managerPhone") or "",
            "homepage": m.get("homepage") or "",
            "lat": float(m["ypos"]) if m.get("ypos") else None,
            "lng": float(m["xpos"]) if m.get("xpos") else None,
            "photoUrl": (f"{_BASE}/coHouse/cmmn/file/fileDown.do?"
                         f"atchFileId={file_id}&fileSn={c.get('fileSn') or 1}")
                        if file_id else "",
        })

    cache = {
        "fetched_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "source": "soco.seoul.go.kr (서울시 청년안심주택)",
        "count": len(complexes),
        "with_coords": sum(1 for c in complexes if c["lat"]),
        "complexes": complexes,
    }
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=1),
                          encoding="utf-8")
    return cache


def load_cache(cache_path: pathlib.Path = CACHE_PATH) -> dict | None:
    if not cache_path.exists():
        return None
    try:
        return json.loads(cache_path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 — 깨진 캐시는 없는 것으로
        return None
