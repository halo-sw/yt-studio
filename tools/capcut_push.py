"""tools/capcut_push.py — edit_plan.json → CapCut 드래프트 자동 조립 (노트북용).

사용법 (노트북에서, GUIDELINE §4-1-3):
  1) CapCutAPI 서버 실행 (github.com/sun-guannan/CapCutAPI 또는 포크):
       python capcut_server.py          # 기본 http://127.0.0.1:9001
  2) 파이프라인 산출 플랜을 밀어넣기:
       python tools/capcut_push.py data/assets/produce/{슬러그}/edit_plan.json
  3) 생성된 dfd_* 드래프트 폴더를 CapCut 초안 디렉토리로 복사 → CapCut에서 열어
     미세조정 → 내보내기(사람 클릭 = 게이트 2 유지).

원칙 (GUIDELINE §4-1-3):
- 이 스크립트는 CapCut '서버'를 호출하지 않는다 — 로컬 CapCutAPI가 드래프트
  '파일'을 만들 뿐이다 (MJ/Higgsfield류 서비스 자동화와 다른 리스크 클래스).
- 반입 소재는 우리 산출물(씬 세그먼트·자체 BGM)만. CapCut 클라우드 에셋 미사용.
- 씬 자막은 세그먼트에 번인돼 있다 — 자막 수정은 대본 수정 후 부분 재렌더가 정석
  (규칙 1-5-2). 여기서는 컷 단위(재배열·트림·효과) 편집이 목적.

주의: 엔드포인트 이름·페이로드는 CapCutAPI 버전/포크에 따라 다를 수 있다.
실패 시 서버 README의 엔드포인트 표와 아래 ENDPOINTS를 맞춰라.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import requests

DEFAULT_BASE = "http://127.0.0.1:9001"

# CapCutAPI(sun-guannan 계열) 표준 엔드포인트 — 포크에 따라 조정 지점
ENDPOINTS = {
    "create": "/create_draft",
    "add_video": "/add_video",
    "add_audio": "/add_audio",
    "save": "/save_draft",
}


def _post(base: str, path: str, payload: dict) -> dict:
    r = requests.post(base + path, json=payload, timeout=120)
    r.raise_for_status()
    data = r.json()
    if isinstance(data, dict) and data.get("success") is False:
        raise RuntimeError(f"{path} 실패: {data.get('error', data)}")
    return data if isinstance(data, dict) else {"raw": data}


def push(plan_path: str, base: str = DEFAULT_BASE, vertical: bool = False) -> None:
    plan = json.loads(Path(plan_path).read_text(encoding="utf-8"))
    width, height = (1080, 1920) if vertical else (plan["width"], plan["height"])

    print(f"1) 드래프트 생성 ({width}x{height})")
    created = _post(base, ENDPOINTS["create"], {"width": width, "height": height})
    draft_id = (created.get("output") or created).get("draft_id") or created.get("draft_id")
    if not draft_id:
        raise SystemExit(f"draft_id를 응답에서 찾지 못함: {created} — ENDPOINTS 확인")

    print(f"2) 씬 세그먼트 {len(plan['scenes'])}개 배치")
    for sc in plan["scenes"]:
        seg = Path(sc["segment"]).resolve()
        if not seg.exists():
            print(f"   ⚠ 세그먼트 없음, 건너뜀: {seg}")
            continue
        _post(base, ENDPOINTS["add_video"], {
            "draft_id": draft_id,
            "video_url": str(seg),          # 로컬 경로 — 포크에 따라 file:// 필요할 수 있음
            "start": 0,
            "end": sc["duration"],
            "target_start": sc["start"],
        })

    if plan.get("bgm"):
        print("3) BGM 트랙 (에피소드 글로벌, 규칙 1-5-1)")
        _post(base, ENDPOINTS["add_audio"], {
            "draft_id": draft_id,
            "audio_url": str(Path(plan["bgm"]).resolve()),
            "start": 0,
            "end": plan["total_duration"],
            "target_start": 0,
            "volume": 0.25,                  # -26 LUFS 언더베드 근사 — CapCut에서 미세조정
        })

    print("4) 드래프트 저장")
    saved = _post(base, ENDPOINTS["save"], {"draft_id": draft_id})
    print(f"   완료 → {saved}")
    print("   dfd_* 폴더를 CapCut 초안 디렉토리로 복사 후 CapCut에서 열기.")
    print("   내보내기는 사람이 (게이트 2). 자막 수정은 대본 수정→부분 재렌더가 정석.")


def main() -> None:
    ap = argparse.ArgumentParser(description="edit_plan.json → CapCut 드래프트 조립")
    ap.add_argument("plan", help="produce가 생성한 edit_plan.json 경로")
    ap.add_argument("--base", default=DEFAULT_BASE, help="CapCutAPI 서버 주소")
    ap.add_argument("--vertical", action="store_true", help="9:16 쇼츠 드래프트")
    args = ap.parse_args()
    try:
        push(args.plan, args.base, args.vertical)
    except requests.ConnectionError:
        sys.exit(f"CapCutAPI 서버에 연결 실패({args.base}) — capcut_server.py 실행 확인")


if __name__ == "__main__":
    main()
