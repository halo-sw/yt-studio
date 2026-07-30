"""심리 5편 「내가 예민한 걸까? — 가스라이팅」 카드 빌더. 대본 31행=31씬.
공식 동일: e5_ 전용 이라스토야 + 전용 감정 영상 + 마스코트 CTA(씬21).
실행: .venv/bin/python -m tracks.psychology.build_ep05"""
from __future__ import annotations
from pathlib import Path
from tracks.psychology import cards, irasutoya

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data/assets/psychology/ep05"
CHIP = "사람 설명서"

CAST: dict[str, tuple[str, str]] = {
    "doubt":   ("混乱", "女性"),          # 기억 의심·혼란
    "lamp":    ("ランプ", ""),            # 가스등(어원)
    "deny":    ("首を横に振る", ""),      # 부정
    "sigh":    ("呆れる", "女性"),        # 축소·어이없어함
    "blame":   ("責める", "女性"),        # 전가·비난
    "alone":   ("孤立", ""),             # 고립
    "flower":  ("花束", ""),             # 간헐적 다정
    "diary":   ("日記", ""),             # 기록
    "call":    ("電話", "友達"),          # 내 편 다시 연결
    "argue":   ("口論", ""),             # 논쟁
    "feel":    ("気持ち", "女性"),        # 감정 인정
    "scholar": ("心理学者", ""),          # 학자
    "warm":    ("仲良し", ""),            # 건강한 관계
    "self":    ("自信", "女性"),          # 나를 다시 믿음
    "workplace":("パワハラ", ""),         # 직장 가스라이팅
}
MASCOT_SLUG = "mascot"

LIVE: dict[int, str] = {
    13: "s_isolated",   # 고립 신호
    17: "s_realize",    # 건강한 관계 위로/자각
    19: "s_reconnect",  # 방법2 내 편 다시 연결
    28: "s_recover",    # 본인 회복
    29: "s_sunrise",    # 희망
}
STOCK_DIR = ROOT / "data/assets/psychology/ep05_live"

SCENES: list[tuple] = [
    ("focus", "doubt",   "그런 적 없다는데, 내 기억이 틀린 걸까", None),
    ("big",   "doubt",   "당신의 기억·감정에 문제가 있는 게 아닙니다", "정교한 심리 조종 — 가스라이팅", "결론부터"),
    ("big",   "lamp",    "가스등을 몰래 어둡게 하고 '네가 예민한 거다'", "현실이 아니라, 현실을 보는 나를 흔든다", "어원"),
    ("focus", "blame",   "대화 뒤엔 늘 내가 잘못한 기분", "01"),
    ("focus", "deny",    "내 기억을 자꾸 의심하게 된다", "02"),
    ("focus", "sigh",    "내 감정이 늘 과장이라는 말을 듣는다", "03"),
    ("big",   "doubt",   "두 개 이상이면 내 문제가 아니라 상대의 기술", "진단이 아니라, 현실 감각을 지키는 지도", None),
    ("big",   "doubt",   "큰 사건이 아니라, 사소한 부정이 매일 쌓인다", "어느 날 내가 나를 못 믿는 상태에 도착한다", None),
    ("focus", "scholar", "조종하는 사람의 대표적 신호들", None),
    ("big",   "deny",    "신호 1 · 부정 — 본 것, 들은 것을 '없던 일'로", "내 눈과 귀보다 그 사람 말을 믿기 시작한다", "1"),
    ("big",   "sigh",    "신호 2 · 축소 — '그게 뭐 큰일이냐'", "상처는 그대로인데 상처받은 내가 이상해진다", "2"),
    ("big",   "blame",   "신호 3 · 전가 — '다 너 때문이야'", "따지러 갔다가 내가 사과하며 끝난다", "3"),
    ("big",   "alone",   "신호 4 · 고립 — '네 친구·가족이 문제다'", "확인해줄 사람이 사라질수록 그의 말이 유일한 현실", "4"),
    ("big",   "flower",  "신호 5 · 간헐적 다정 — 가끔 예전처럼", "이 드문 다정 때문에 '내가 문제'라 결론 낸다", "5"),
    ("big",   "doubt",   "흔들린 현실 감각을 어떻게 다시 세울까", "왜 이 조종이 사랑처럼 느껴질까 — 지금부터 핵심", None),
    ("big",   "warm",    "당하는 건 어리석어서가 아니다", "믿고, 지키려 하고, 내 탓부터 돌아보는 성숙한 사람일수록 취약", "혹시 본인이라면"),
    ("big",   "warm",    "건강한 관계는 나를 자꾸 의심하게 만들지 않는다", "곁에서 자꾸 내가 흐려진다면 사랑이 아니라 조종의 신호", None),
    ("big",   "diary",   "방법 1 · 현실을 머리 밖에 기록한다", "흔들리는 밤, 그 기록이 나 대신 현실을 붙잡는다", None),
    ("big",   "call",    "방법 2 · 멀어진 내 편을 다시 연결한다", "'내가 미쳐가는 게 아니'라고 확인해줄 한 사람", None),
    ("big",   "argue",   "방법 3 · 이길 수 없는 논쟁을 멈춘다", "진실을 찾는 대화가 아니라 나를 지치게 하는 게임", None),
    ("big",   "mascot",  "내 현실은 내가 안다는 자리에 서 있기", "구독해두시면 다음 편(자존감)이 먼저 도착합니다", None),
    ("big",   "feel",    "벗어난 뒤에도 후유증은 남는다", "작은 결정도 무섭고 감정 느끼는 것조차 어색해진다", None),
    ("big",   "feel",    "회복 연습 · 하루 한 번 내 감정 그냥 인정하기", "옳고 그름 말고 — '지금 나는 서운하다'", None),
    ("big",   "blame",   "이건 연애만이 아니다 — 부모·친구·직장에도", "'너의 현실은 틀렸고 내 말이 맞다'는 구조는 같다", None),
    ("big",   "diary",   "가장 조심할 순간 = 벗어난 뒤 다시 흔들릴 때", "미화된 기억이 아니라, 그날 적어둔 현실을 꺼내라", None),
    ("list",  "mascot",  "흔들린 땅을 다시 다지는 세 문장", [
        "현실을 머리 밖에 기록하자",
        "멀어진 내 편을 다시 연결하자",
        "이길 수 없는 논쟁은 멈추자",
    ]),
    ("big",   "self",    "상대를 설득하는 게 아니라, 나를 다시 믿기 시작하는 것", "벗어남은 이기는 게 아니라 되찾는 것", None),
    ("big",   "self",    "자꾸 내가 이상한 것 같다면", "누군가 계속 그렇게 말해왔기 때문 — 걷어내면 감각은 멀쩡했다", "본인이라면"),
    ("big",   "self",    "현실 감각은 반드시 돌아온다", "'내가 미친 걸까' 대신 '이건 아니었다'고 담담히", None),
    ("big",   "scholar", "이건 지도이지, 모든 갈등에 붙이는 딱지가 아니다", "일상·안전이 무너지는 수준이면 전문가와 이야기하세요", None),
    ("big",   "mascot",  "당신이 예민했던 걸까, 예민하게 만든 걸까", "오늘 떠오른 그 사람 이야기를 댓글로 남겨두세요", "댓글로"),
]


def _cast():
    got = {}
    for slug, (kw, pref) in CAST.items():
        p = irasutoya.fetch(kw, f"e5_{slug}", prefer=pref)
        if p: got[slug] = p
        else: print(f"   ⚠ 누락 {slug} ({kw})")
    print(f"   이라스토야 {len(got)}/{len(CAST)}")
    nm = ROOT / "data/assets/psychology/character/mascot_cut.png"
    from tracks.psychology.brand import mascot_cutout
    got[MASCOT_SLUG] = nm if nm.exists() else mascot_cutout()
    return got


def build():
    lines = [l for l in (ROOT / "data/scripts/psy05_gaslighting.txt").read_text(encoding="utf-8").splitlines() if l.strip()]
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
    hook = ROOT / "data/assets/psychology/character/hook_woman_ep05.mp4"
    if hook.exists(): shutil.copy2(hook, OUT / "1.mp4"); placed += 1
    cta = ROOT / "data/assets/psychology/character/mascot_cta.mp4"
    if cta.exists(): shutil.copy2(cta, OUT / "21.mp4"); placed += 1
    print(f"   실사/애니 {placed} / 카드 {len(SCENES)-placed}")
    return OUT


if __name__ == "__main__":
    build()
