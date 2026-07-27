"""심리 B형 3편 「끝난 이야기가 끝나지 않는 이유 — 자이가르닉 효과」 카드 빌더.

대본: data/scripts/psy03_zeigarnik.txt (40행 = 40씬)
주제: 이별 후 미련 = 미완결(자이가르닉 효과) + 장밋빛 회상. 애착 시리즈와 별개.

공식(ep02와 동일):
  · 이라스토야: ep03 전용(e3_ 슬러그) — ep01/02와 다른 컷, 일본어 검색
  · 실사/감정 씬: 이 스토리 전용 생성(GPT Image 2 + i2v), 스톡·타편 재사용 금지
  · 마스코트 CTA(mascot_cta.mp4)는 브랜드 자산이라 재사용
  · 카드 전면 타이포 → produce --static 전 씬
  · 마지막 예고 없음(사용자 요청) — 씬40은 닫는 위로 + 댓글 CTA

실행: .venv/bin/python -m tracks.psychology.build_ep03
"""
from __future__ import annotations

from pathlib import Path

from tracks.psychology import cards, irasutoya

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data/assets/psychology/ep03"
CHIP = "사람 설명서"

# --- ep03 전용 캐스트 (e3_ 슬러그, 이별/미련 테마 · 일본어 검색) ------------------
CAST: dict[str, tuple[str, str]] = {
    "miss":    ("未練", "女性"),        # 미련·그리움
    "cry":     ("泣く", "女性"),        # 무너짐
    "memory":  ("思い出", ""),          # 추억(좋은 기억)
    "song":    ("音楽", "イヤホン"),    # 노래에 무너짐
    "ponder":  ("考える", "女性"),      # 하지 못한 말·생각
    "scholar": ("心理学者", ""),        # 자이가르닉(학자)
    "waiter":  ("ウェイター", ""),      # 카페 웨이터
    "task":    ("勉強", "女性"),        # 과제(중단 실험)
    "loop":    ("モヤモヤ", ""),        # 머릿속 맴돎(열린 고리)
    "brain":   ("脳", ""),              # 뇌
    "breakup": ("失恋", ""),            # 이별
    "letter":  ("手紙", "書く"),        # 편지(종결 의식)
    "note":    ("メモ", "女性"),        # 기억 재평가 메모
    "block":   ("スマホ", "削除"),      # 연락 끊기·차단
    "newgoal": ("目標", ""),            # 새 고리(새 목표)
}

MASCOT_SLUG = "mascot"

# --- 실사/감정 씬 (ep03 전용 생성 — data/assets/psychology/ep03_live/) --------------
LIVE: dict[int, str] = {
    2:  "s02_empty_bed",     # 결론/대비 — 텅 빈 옆자리(강제 미완결)
    19: "s19_night_selfblame",  # 자책하지 마세요 — 어두운 방, 폰 들고 망설임
    27: "s27_volume_down",   # 볼륨처럼 서서히 — 창밖, 조금 편안해진 표정
    33: "s33_rose_memory",   # 미화된 기억 — 빛바랜 사진을 바라봄
    38: "s38_sunrise_hope",  # 반드시 닫힌다 — 일출, 편안한 미소
}
STOCK_DIR = ROOT / "data/assets/psychology/ep03_live"

# --- 씬 → 카드 매핑 (대본 40행과 1:1) ---------------------------------------
SCENES: list[tuple] = [
    ("focus", "miss",     "몇 달이 지났는데, 왜 지금 더 선명할까", None),
    ("big",   "cry",      "당신이 아직 그 사람을 사랑해서가 아닙니다", "", "결론부터"),
    ("focus", "mascot",   "오늘의 주제 · 자이가르닉 효과", None),
    ("focus", "memory",   "좋은 점만 자꾸 떠오른다", "01"),
    ("focus", "song",     "노래·거리·냄새 하나에 무너진다", "02"),
    ("focus", "ponder",   "하지 못한 말이 머릿속을 맴돈다", "03"),
    ("big",   "note",     "두 개 이상이면 사랑이 아니라 미완결", "진단이 아니라, 이해를 위한 지도입니다", None),
    ("focus", "scholar",  "블루마 자이가르닉 · 1920년대", None),
    ("big",   "waiter",   "계산 전 주문은 기억, 계산 후엔 잊는다", "끝난 일은 지워지고, 끝나지 않은 일만 남았다", None),
    ("focus", "task",     "끝까지 한 과제 vs 중간에 멈춘 과제", None),
    ("big",   "task",     "끊긴 과제를 두 배 더 잘 기억했다", "뇌는 끝나지 않은 일에만 표시를 남긴다", "실험 결과"),
    ("focus", "loop",     "뇌는 '열린 고리'를 싫어한다", None),
    ("big",   "brain",    "미완결을 떠올릴 때 뇌가 더 활발했다", "끝나지 않은 일은 뇌 안에서 계속 불이 켜져 있다", "근거"),
    ("big",   "breakup",  "이별은 가장 크게 열린 고리다", "한쪽이 정리되기 전에 강제로 끝나는 미완결", "반전"),
    ("big",   "miss",     "그래서 뇌가 자꾸 그 사람을 불러온다", "그리움처럼 느껴지지만, 미완결을 끝내려는 작업", None),
    ("big",   "memory",   "나빴던 건 흐려지고 좋았던 것만 선명해진다", "심리학 용어로 — 장밋빛 회상", None),
    ("big",   "ponder",   "우리는 사람이 아니라 미완결을 그리워한다", "지금부터가 오늘의 핵심입니다", None),
    ("big",   "miss",     "미련이 길다고 미련한 게 아닙니다", "진심으로 열었던 고리일수록 닫는 데 시간이 걸린다", "혹시 본인이라면"),
    ("big",   "cry",      "생각난다고 자책하지 마세요", "고리를 닫으려는 건 고장이 아니라 정상 작동", None),
    ("big",   "block",    "가장 쉬운 닫기 = 다시 연결, 그러나…", "이렇게 닫은 고리는 다음 날 더 크게 열린다", "잘못된 방법"),
    ("focus", "letter",   "방법 1 · 종결 의식", "01"),
    ("big",   "letter",   "부치지 않을 편지를 끝까지 쓴다", "편지의 진짜 독자는 그 사람이 아니라 당신의 뇌", None),
    ("focus", "note",     "방법 2 · 기억 재평가", "02"),
    ("big",   "note",     "미화된 기억 옆에 '진짜'를 나란히 둔다", "헤어진 이유 세 가지를 적어 저장해두기", None),
    ("focus", "block",    "방법 3 · 새 신호 차단", "03"),
    ("big",   "block",    "계정을 지우는 건 미련이 아니라 어른의 선택", "보이지 않아야 뇌도 고리를 내려놓는다", None),
    ("big",   "cry",      "왜 하루아침에 안 될까", "고리는 스위치가 아니라 볼륨처럼 서서히 줄어든다", None),
    ("big",   "mascot",   "가장 중요한 마지막 방법이 남았습니다", "구독해두시면 다음 편이 먼저 도착합니다", None),
    ("focus", "newgoal",  "방법 4 · 새로운 고리 열기", "04"),
    ("big",   "newgoal",  "옛 고리 대신 몰두할 새 미완결을 연다", "다만 그게 곧바로 다른 사람일 필요는 없다", None),
    ("big",   "loop",     "끝맺지 못한 것은 삶 곳곳에 걸려 있다", "그만둔 회사, 멀어진 친구, 이루지 못한 꿈", None),
    ("big",   "letter",   "핵심은 잊는 게 아니라 닫는 것", "잊으려 할수록 뇌는 그걸 더 붙잡는다", None),
    ("big",   "memory",   "미완결과 미화가 겹칠 때가 가장 힘들다", "존재한 적 없는 완벽한 사람을 그리워하게 된다", "가장 잔인한 조합"),
    ("focus", "mascot",   "오늘 밤 바로 쓸 수 있는 세 가지", None),
    ("list",  "mascot",   "미련이 밀려오는 밤에", [
        "부치지 않을 편지를 끝까지 쓴다",
        "헤어진 이유 세 가지를 옆에 둔다",
        "몰두할 새 고리 하나를 오늘 연다",
    ]),
    ("big",   "letter",   "전부 잊는 게 아니라 하나씩 닫는 일", "미련은 지워 없애는 게 아니라 끝맺어 흘려보내는 것", None),
    ("big",   "ponder",   "생각난다 = 아직 안 닫혔다는 뜻", "그 순간부터 당신 자신의 회복을 돌볼 수 있다", "본인이라면"),
    ("big",   "miss",     "이 고리는 반드시 닫힙니다", "매일이 일주일에 한 번이 되고, 문득 오래 생각나지 않는 날이 온다", None),
    ("big",   "cry",      "이건 지도이지, 감정을 잘라내는 설명서가 아닙니다", "상실이 일상을 오래 짓누르면 전문가와 이야기하세요", None),
    ("big",   "mascot",   "끝맺지 못한 이야기, 누구에게나 있어요", "오늘 떠오른 그 사람은 아직 닫지 못한 어떤 고리였나요", "댓글로 남겨두세요"),
]


def _cast() -> dict[str, Path]:
    got: dict[str, Path] = {}
    for slug, (kw, prefer) in CAST.items():
        p = irasutoya.fetch(kw, f"e3_{slug}", prefer=prefer)
        if p:
            got[slug] = p
        else:
            print(f"   ⚠ 캐스트 누락: {slug} ({kw}) — 키워드 재지정 필요")
    limit = irasutoya.FREE_LIMIT_PER_VIDEO
    n = len(got)
    print(f"   이라스토야 {n}/{len(CAST)}점 (무료 한도 {limit}점, 여유 {limit - n}점)")
    if n > limit:
        raise SystemExit(f"고유 소재 {n}점 — 무료 한도 {limit}점 초과. 캐스트를 줄일 것")

    new_mascot = ROOT / "data/assets/psychology/character/mascot_cut.png"
    from tracks.psychology.brand import mascot_cutout
    got[MASCOT_SLUG] = new_mascot if new_mascot.exists() else mascot_cutout()
    print(f"   마스코트 → {got[MASCOT_SLUG].name}")
    return got


def build() -> Path:
    lines = (ROOT / "data/scripts/psy03_zeigarnik.txt").read_text(encoding="utf-8").splitlines()
    n_lines = len([l for l in lines if l.strip()])
    if len(SCENES) != n_lines:
        raise SystemExit(f"씬 매핑 {len(SCENES)}개 ≠ 대본 {n_lines}행")

    print("1) 이라스토야 전용 캐스트 확보")
    cast = _cast()
    fallback = next(iter(cast.values()))

    print("2) 카드 렌더")
    OUT.mkdir(parents=True, exist_ok=True)
    for i, spec in enumerate(SCENES, start=1):
        kind, slug = spec[0], spec[1]
        il = cast.get(slug, fallback)
        out = OUT / f"{i}.png"
        if kind == "focus":
            cards.focus_frame(il, out, headline=spec[2], num=spec[3], chip=CHIP)
        elif kind == "big":
            cards.big_card(spec[2], spec[3], il, out, accent=spec[4], chip=CHIP)
        elif kind in ("bad", "good"):
            cards.quote_frame(spec[2], good=(kind == "good"), illust=il, out=out, chip=CHIP)
        elif kind == "list":
            cards.list_card(spec[2], spec[3], out, illust=il, chip=CHIP)
        else:
            raise SystemExit(f"씬 {i}: 알 수 없는 카드 종류 {kind}")
    print(f"   → {OUT} ({len(SCENES)}장)")

    print("3) 실사/감정 씬 배치")
    import shutil
    for old in OUT.glob("*.mp4"):
        old.unlink()
    placed = 0
    for sid, name in LIVE.items():
        src = STOCK_DIR / f"{name}.mp4"
        if not src.exists():
            print(f"   ⚠ 씬 {sid}: {name}.mp4 없음 — 카드로 대체됨")
            continue
        shutil.copy2(src, OUT / f"{sid}.mp4")
        placed += 1
    hook = ROOT / "data/assets/psychology/character/hook_woman_ep03.mp4"
    if hook.exists():
        shutil.copy2(hook, OUT / "1.mp4")
        placed += 1
        print("   씬1 훅 → hook_woman_ep03.mp4")
    cta = ROOT / "data/assets/psychology/character/mascot_cta.mp4"
    if cta.exists():
        shutil.copy2(cta, OUT / "28.mp4")
        placed += 1
        print("   씬28 CTA → mascot_cta.mp4 (재사용)")
    print(f"   실사/애니 {placed}씬 / 카드 {len(SCENES) - placed}씬")

    static = ",".join(str(i) for i in range(1, len(SCENES) + 1))
    print("\n다음: produce --reuse-audio 아님(신규 TTS) --static", static[:20], "...")
    return OUT


if __name__ == "__main__":
    build()
