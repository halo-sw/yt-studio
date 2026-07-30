"""심리 6편 「자꾸 휘둘리고 착하기만 한 사람의 심리 — 자존감」 카드 빌더. 대본 34행=34씬.
공식 동일: e6_ 전용 이라스토야 + 전용 감정 영상 + 마스코트 CTA(씬26).
실행: .venv/bin/python -m tracks.psychology.build_ep06"""
from __future__ import annotations
from pathlib import Path
from tracks.psychology import cards, irasutoya

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data/assets/psychology/ep06"
CHIP = "사람 설명서"

CAST: dict[str, tuple[str, str]] = {
    "refuse":  ("断れない", "女性"),      # 거절 못함
    "eyes":    ("顔色をうかがう", ""),    # 눈치
    "humble":  ("謙遜", "女性"),          # 칭찬 못 받음(과한 겸손)
    "parent":  ("成績", "親子"),          # 조건부 사랑
    "critic":  ("自己嫌悪", ""),          # 내면의 비판자
    "compare": ("比較", "女性"),          # 비교
    "sns":     ("スマホ", "見て落ち込"),  # SNS 비교
    "office":  ("残業", "女性"),          # 직장에서 떠맡음
    "cheer":   ("自分を励ます", ""),      # 자기 연민
    "sayno":   ("断る", "女性"),          # 거절 연습
    "voice":   ("心の声", ""),            # 내면의 목소리
    "scholar": ("心理学者", ""),          # 학자
    "hug":     ("ハグ", ""),              # 나를 안아주기
    "care":    ("自分を大切", ""),        # 나를 아끼기
    "cup":     ("コップ", "水"),          # 내 잔을 먼저 채우기
}
MASCOT_SLUG = "mascot"

LIVE: dict[int, str] = {
    19: "s_selfcompassion",  # 방법1 자기연민
    21: "s_boundary",        # 방법2 작은 거절
    31: "s_recover",         # 본인 회복
    32: "s_sunrise",         # 희망
}
STOCK_DIR = ROOT / "data/assets/psychology/ep06_live"

SCENES: list[tuple] = [
    ("focus", "refuse",  "거절을 못 해서 또 떠맡았다", None),
    ("big",   "critic",  "착하거나 예민해서가 아닙니다", "자기 가치를 낮게 매기는 습관 — 낮은 자존감", "결론부터"),
    ("big",   "care",    "자신감 = 잘한다는 느낌 / 자존감 = 못해도 소중하다는 감각", "그래서 많이 이뤄도 자존감 낮으면 늘 허기진다", None),
    ("focus", "refuse",  "거절도, 부탁도 못 한다", "01"),
    ("focus", "eyes",    "남의 눈치·평가에 하루가 휘둘린다", "02"),
    ("focus", "humble",  "잘돼도 내 덕이 아니라 여긴다", "03"),
    ("big",   "critic",  "두 개 이상이면 착한 게 아니라 자존감이 낮은 상태", "흠이 아니라, 나를 되찾기 위한 지도", None),
    ("big",   "parent",  "자존감은 어릴 때 조건 속에서 만들어진다", "잘할 때만 사랑받으면, 나는 해내야만 사랑받을 자격이 생긴다고 배운다", None),
    ("big",   "parent",  "백 점엔 웃어주고, 아흔 점엔 나머지 열 점을 묻는다", "사랑은 내 존재가 아니라 성적에 붙는 거구나", None),
    ("big",   "critic",  "어른이 되면 마음속에 엄격한 목소리가 산다", "심리학 용어로 — 내면의 비판자", None),
    ("big",   "critic",  "이 목소리는 나를 지키려다 생겼다", "어른이 된 뒤엔 나를 보호하지 않고 갉아먹기 시작한다", None),
    ("big",   "humble",  "그래서 칭찬을 들어도 그냥 못 받는다", "'아니에요'는 겸손이 아니라, 자격 없다는 오래된 믿음", None),
    ("big",   "sns",     "여기에 비교가 얹힌다", "수천 명의 가장 좋은 순간과 나의 가장 초라한 순간을 비교한다", None),
    ("big",   "sns",     "남의 편집된 예고편에 나만 뒤처졌다 느낀다", "비교라는 게임엔 이기는 사람이 아무도 없다", None),
    ("big",   "critic",  "낮은 자존감은 관계에서도 티가 난다", "나를 함부로 대하는 사람도 못 끊고 인정을 구걸한다 (나르시시스트에게 잘 걸려드는 이유)", None),
    ("big",   "office",  "직장에서도 부당한 일을 떠맡고 인정만 기다린다", "마음을 내주고 돌아오는 건 더 만만해 보이는 시선", None),
    ("big",   "care",    "깎여나간 자존감을 어떻게 다시 세울까", "왜 남에겐 관대하면서 나에게만 가혹할까 — 지금부터 핵심", None),
    ("big",   "care",    "자존감은 최고라고 우기는 게 아니다", "못난 점까지 포함해 '그래도 존재할 가치가 있다' — 첫걸음은 나에게 다정해지기", None),
    ("big",   "cheer",   "방법 1 · 나를 친구처럼 대한다(자기 연민)", "실수한 나에게 '그럴 수도 있지, 많이 애썼어'", None),
    ("big",   "cheer",   "친구에겐 '넌 역시 안 돼'라 안 하잖아요", "남에게 준 그 다정함을, 딱 그만큼 나에게도", None),
    ("big",   "sayno",   "방법 2 · 아주 작은 거절을 연습한다", "거절해도 관계가 안 무너지는 경험이 쌓이면 몸이 배운다", None),
    ("big",   "sayno",   "처음의 죄책감은 잘못이 아니라 근육의 뻐근함", "몇 번만 견디면 거절은 관계를 솔직하게 만든다", None),
    ("big",   "voice",   "방법 3 · 내면의 비판자에게 대꾸한다", "'넌 역시 안 돼'는 사실이 아니라 낡은 녹음일 뿐", None),
    ("big",   "sns",     "방법 4 · 비교의 스위치를 내린다", "화면 속은 예고편 — '저건 예고편'이라 한 번만 되뇌기", None),
    ("big",   "care",    "왜 이렇게 어려울까 — 수십 년 쌓인 습관이라서", "한 번에 말고, 오늘 다정한 말 한마디·작은 거절 하나의 반복", None),
    ("big",   "mascot",  "마음이 무거워졌다면 잠깐", "구독해두시면 다음 편도 같이 공부할 수 있어요", None),
    ("big",   "care",    "자존감이 회복되면 가장 먼저 관계가 달라진다", "나를 함부로 대하는 사람이 예전만큼 편하지 않아진다", None),
    ("big",   "cup",     "이건 이기적인 게 아니다", "내 잔이 비면 남에게 따라줄 것도 없다 — 나를 채우는 건 관계의 기본기", None),
    ("list",  "mascot",  "무너진 자존감을 세우는 세 문장", [
        "실수한 나에게 친구처럼 말하자",
        "아주 작은 거절부터 연습하자",
        "비교엔 '저건 예고편'이라 되뇌자",
    ]),
    ("big",   "hug",     "전부 더 잘나지려는 게 아니다", "있는 그대로의 나를 더 다정하게 — 자존감은 부족한 나를 받아들이는 데서 자란다", None),
    ("big",   "care",    "자꾸 작아진다면, 스스로를 너무 오래 깎아온 것", "그 습관을 내려놓으면 원래 크기로 천천히 돌아온다", "본인이라면"),
    ("big",   "care",    "자존감은 반드시 다시 자란다", "남의 눈치가 아니라 내 마음을 기준으로 사는 나 — 그날의 당신은 훨씬 편안하다", None),
    ("big",   "scholar", "이건 지도이지, 혼자 다 해내라는 숙제가 아니다", "무거움이 일상을 오래 짓누르면 전문가의 도움을 받을 신호", None),
    ("big",   "mascot",  "당신이 당신에게 가장 해주고 싶은 말은?", "그 한마디를 댓글로 남겨두면, 나를 아끼는 연습은 이미 시작", "댓글로"),
]


def _cast():
    got = {}
    for slug, (kw, pref) in CAST.items():
        p = irasutoya.fetch(kw, f"e6_{slug}", prefer=pref)
        if p: got[slug] = p
        else: print(f"   ⚠ 누락 {slug} ({kw})")
    print(f"   이라스토야 {len(got)}/{len(CAST)}")
    nm = ROOT / "data/assets/psychology/character/mascot_cut.png"
    from tracks.psychology.brand import mascot_cutout
    got[MASCOT_SLUG] = nm if nm.exists() else mascot_cutout()
    return got


def build():
    lines = [l for l in (ROOT / "data/scripts/psy06_selfesteem.txt").read_text(encoding="utf-8").splitlines() if l.strip()]
    if len(SCENES) != len(lines): raise SystemExit(f"씬 {len(SCENES)} ≠ 대본 {len(lines)}")
    print("1) 캐스트"); cast = _cast(); fb = next(iter(cast.values()))
    print("2) 카드"); OUT.mkdir(parents=True, exist_ok=True)
    for i, spec in enumerate(SCENES, 1):
        kind, slug = spec[0], spec[1]; il = cast.get(slug, fb); out = OUT / f"{i}.png"
        if kind == "focus": cards.focus_frame(il, out, headline=spec[2], num=spec[3], chip=CHIP)
        elif kind == "big": cards.big_card(spec[2], spec[3], il, out, accent=spec[4], chip=CHIP)
        elif kind == "list": cards.list_card(spec[2], spec[3], out, illust=il, chip=CHIP)
    print(f"   → {OUT} ({len(SCENES)})")
    print("3) 실사 배치"); import shutil
    for old in OUT.glob("*.mp4"): old.unlink()
    placed = 0
    for sid, name in LIVE.items():
        src = STOCK_DIR / f"{name}.mp4"
        if src.exists(): shutil.copy2(src, OUT / f"{sid}.mp4"); placed += 1
    hook = ROOT / "data/assets/psychology/character/hook_woman_ep06.mp4"
    if hook.exists(): shutil.copy2(hook, OUT / "1.mp4"); placed += 1
    cta = ROOT / "data/assets/psychology/character/mascot_cta.mp4"
    if cta.exists(): shutil.copy2(cta, OUT / "26.mp4"); placed += 1
    print(f"   실사/애니 {placed} / 카드 {len(SCENES)-placed}")
    return OUT


if __name__ == "__main__":
    build()
