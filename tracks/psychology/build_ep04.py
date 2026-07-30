"""심리 4편 「완벽했던 그 사람이 나를 미치게 하는 이유 — 나르시시스트」 카드 빌더.
대본: data/scripts/psy04_narcissist.txt (35행=35씬). 트렌드 주제(자기애성 연애).
공식 동일: e4_ 전용 이라스토야 + 전용 감정 영상(스톡·타편 재사용 금지) + 마스코트 CTA 재사용.
실행: .venv/bin/python -m tracks.psychology.build_ep04
"""
from __future__ import annotations
from pathlib import Path
from tracks.psychology import cards, irasutoya

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data/assets/psychology/ep04"
CHIP = "사람 설명서"

CAST: dict[str, tuple[str, str]] = {
    "charm":   ("プレゼント", "女性"),     # 러브바밍(선물·과한 애정)
    "apolo":   ("謝る", "女性"),           # 내가 사과
    "sneer":   ("見下す", ""),             # 경멸·평가절하
    "mask":    ("仮面", ""),               # 가면(속은 얕음)
    "down":    ("落ち込む", "女性"),       # 무너지는 나
    "confuse": ("混乱", "女性"),           # 가스라이팅 혼란
    "gamble":  ("スロット", ""),           # 간헐강화·중독(도박)
    "poker":   ("真顔", "女性"),           # 회색 돌(무반응)
    "block":   ("削除", "スマホ"),         # 무접촉·차단
    "diary":   ("日記", ""),               # 사실 기록
    "scholar": ("研究者", "白衣"),         # 연구자
    "happy":   ("カップル", "幸せ"),       # 이상화(행복한 커플)
    "turnaway":("背を向ける", ""),         # 버림·돌아섬
    "mirror":  ("鏡", "女性"),             # 나를 비추는 거울
    "standup": ("立ち上がる", ""),         # 회복·일어섬
}
MASCOT_SLUG = "mascot"

LIVE: dict[int, str] = {
    2:  "s02_realize",       # 결론 — 문득 알아차리는 여성
    13: "s13_reach_pull",    # 트라우마 본딩 — 붙잡으려는데 멀어짐
    18: "s18_selfcomfort",   # 자책 내려놓기 — 스스로 다독임
    29: "s29_recover",       # 회복 — 창가서 중심 되찾기
    33: "s33_sunrise",       # 희망 — 일출, 단단해진 미소
}
STOCK_DIR = ROOT / "data/assets/psychology/ep04_live"

SCENES: list[tuple] = [
    ("focus", "confuse",  "완벽했던 사람이 나를 이상하게 만든다", None),
    ("big",   "mask",     "당신이 예민한 게 아닙니다", "그 사람은 나르시시스트일 수 있어요", "결론부터"),
    ("focus", "mask",     "오늘의 주제 · 나르시시스트", None),
    ("focus", "charm",    "초반이 지나치게 완벽했다 — 러브 바밍", "01"),
    ("focus", "apolo",    "모든 문제가 내 탓이 된다", "02"),
    ("focus", "happy",    "떠나려 하면 갑자기 예전으로 돌아온다", "03"),
    ("big",   "confuse",  "두 개 이상이면 사랑이 아니라 조종", "진단이 아니라, 나를 지키는 지도입니다", None),
    ("big",   "mask",     "과장된 자기 · 인정에 굶주림 · 공감의 결여", "겉은 당당, 속은 얕은 유리", None),
    ("big",   "mirror",   "연인은 사랑의 대상이 아니라, 나를 비출 거울", "거울이 흐려지는 순간 태도가 돌변한다", None),
    ("focus", "scholar",  "학대의 세 단계 · 이상화 → 평가절하 → 버림", None),
    ("big",   "happy",    "1단계 이상화 — 운명의 상대가 된다", "도파민 폭발, 벗어나기 힘든 이유가 여기서 시작", "1단계"),
    ("big",   "sneer",    "2단계 평가절하 — 칭찬이 비교로, 애정이 비난으로", "잃어버린 처음을 되찾으려 더 애쓰게 된다", "2단계"),
    ("big",   "turnaway", "3단계 버림 — 지치게 한 뒤 차갑게", "완전히 떠나려 하면 다시 이상화로 붙잡는다", "3단계"),
    ("big",   "gamble",   "힘들수록 더 놓기 어렵다 — 트라우마 본딩", "간헐적 다정함은 도박의 잭팟처럼 작동한다", "가장 아픈 진실"),
    ("big",   "gamble",   "의지가 약해서가 아니라, 뇌 보상회로가 납치당한 것", "언제 올지 모르니 더 매달린다", None),
    ("big",   "confuse",  "관계를 유지시키는 도구 = 가스라이팅", "그런 적 없다, 네가 예민한 거다 — 다음 편에서 깊게", None),
    ("big",   "mask",     "이 회전문에서 어떻게 내려올까", "왜 좋은 사람이 자꾸 걸려드는가 — 지금부터 핵심", None),
    ("big",   "down",     "걸려드는 건 어리석어서가 아니다", "공감 높고 정 많은 사람이 가장 이용당하기 쉽다", "혹시 본인이라면"),
    ("big",   "down",     "자책부터 내려놓으세요", "속인 건 당신이 순진해서가 아니라, 상대가 능숙했기 때문", None),
    ("big",   "apolo",    "방법 1 · 고치려는 시도를 멈춘다", "헌신은 변화가 아니라 관계를 끄는 연료가 된다", None),
    ("big",   "poker",    "방법 2 · 반응을 줄인다 — 회색 돌 되기", "감정 반응은 나르시시스트의 먹이", None),
    ("big",   "diary",    "방법 3 · 사실을 기록한다", "흔들리는 밤, 그 기록이 착각이 아님을 붙잡아준다", None),
    ("big",   "gamble",   "떠나기 어려운 건 중독과 같은 상태", "그리운 건 그 사람이 아니라 이상화의 환상", None),
    ("big",   "mascot",   "방법 4 · 접촉을 완전히 끊는다(무접촉)", "구독해두시면 다음 편이 먼저 도착합니다", None),
    ("big",   "mirror",   "끝난 뒤 밉기보다 내가 초라하다면", "가치가 깎이고 판단이 흔들렸으니 당연하다", None),
    ("big",   "standup",  "회복은 내 감각을 다시 믿는 연습", "작은 것부터 '내가 느낀 게 맞다'고 인정하기", None),
    ("big",   "sneer",    "나르시시스트는 부모·친구·상사일 수도", "이름은 달라도 나를 도구로 쓰는 패턴은 같다", None),
    ("big",   "diary",    "가장 조심할 순간 = 끝난 뒤의 자기 의심", "흔들리는 밤을 위해 기록과 오늘 이야기를 붙잡아라", None),
    ("focus", "standup",  "오늘 쓸 수 있는 세 문장", None),
    ("list",  "mascot",   "회전문에서 내려오는 계단", [
        "고치려 말고 나를 지키자",
        "감정 먹이를 끊고, 사실을 기록하자",
        "회복을 위해 완전히 끊자",
    ]),
    ("big",   "poker",    "이기는 유일한 방법 = 그 게임에 참여하지 않기", "상대를 바꾸는 게 아니라 나를 안전하게 꺼내는 것", None),
    ("big",   "mirror",   "자꾸 작아졌다면, 누군가 당신을 깎고 있던 것", "그 손에서 벗어나면 원래 크기로 돌아온다", "본인이라면"),
    ("big",   "standup",  "회복은 반드시 찾아온다", "사라진 건 사랑이 아니라 안개, 그 자리에 당신이 서 있다", None),
    ("big",   "scholar",  "이건 지도이지, 함부로 붙이는 딱지가 아니다", "안전을 위협받는 수준이면 전문가·주변의 도움을", None),
    ("big",   "mascot",   "그 사람은 당신을 사랑한 걸까, 이용한 걸까", "오늘 떠오른 그 관계 이야기를 댓글로 남겨두세요", "댓글로"),
]


def _cast() -> dict[str, Path]:
    got = {}
    for slug, (kw, prefer) in CAST.items():
        p = irasutoya.fetch(kw, f"e4_{slug}", prefer=prefer)
        if p:
            got[slug] = p
        else:
            print(f"   ⚠ 누락: {slug} ({kw})")
    n = len(got)
    print(f"   이라스토야 {n}/{len(CAST)}점 (한도 {irasutoya.FREE_LIMIT_PER_VIDEO})")
    new_mascot = ROOT / "data/assets/psychology/character/mascot_cut.png"
    from tracks.psychology.brand import mascot_cutout
    got[MASCOT_SLUG] = new_mascot if new_mascot.exists() else mascot_cutout()
    return got


def build() -> Path:
    lines = [l for l in (ROOT / "data/scripts/psy04_narcissist.txt").read_text(encoding="utf-8").splitlines() if l.strip()]
    if len(SCENES) != len(lines):
        raise SystemExit(f"씬 {len(SCENES)} ≠ 대본 {len(lines)}행")
    print("1) 캐스트"); cast = _cast(); fb = next(iter(cast.values()))
    print("2) 카드"); OUT.mkdir(parents=True, exist_ok=True)
    for i, spec in enumerate(SCENES, 1):
        kind, slug = spec[0], spec[1]; il = cast.get(slug, fb); out = OUT / f"{i}.png"
        if kind == "focus": cards.focus_frame(il, out, headline=spec[2], num=spec[3], chip=CHIP)
        elif kind == "big": cards.big_card(spec[2], spec[3], il, out, accent=spec[4], chip=CHIP)
        elif kind in ("bad", "good"): cards.quote_frame(spec[2], good=(kind == "good"), illust=il, out=out, chip=CHIP)
        elif kind == "list": cards.list_card(spec[2], spec[3], out, illust=il, chip=CHIP)
    print(f"   → {OUT} ({len(SCENES)})")
    print("3) 실사/감정 배치"); import shutil
    for old in OUT.glob("*.mp4"): old.unlink()
    placed = 0
    for sid, name in LIVE.items():
        src = STOCK_DIR / f"{name}.mp4"
        if src.exists(): shutil.copy2(src, OUT / f"{sid}.mp4"); placed += 1
        else: print(f"   ⚠ 씬{sid} {name}.mp4 없음")
    hook = ROOT / "data/assets/psychology/character/hook_woman_ep04.mp4"
    if hook.exists(): shutil.copy2(hook, OUT / "1.mp4"); placed += 1
    cta = ROOT / "data/assets/psychology/character/mascot_cta.mp4"
    if cta.exists(): shutil.copy2(cta, OUT / "24.mp4"); placed += 1
    print(f"   실사/애니 {placed} / 카드 {len(SCENES)-placed}")
    return OUT


if __name__ == "__main__":
    build()
