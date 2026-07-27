"""심리 B형 2편 「매달릴수록 멀어진다 — 불안형 애착」 카드 빌더.

대본: data/scripts/psy02_anxious.txt (40행 = 40씬, ≈10.9분 @8.67자/초)
출력: data/assets/psychology/ep02/{1..40}.png → cli.py produce --images 로 주입

ep01(회피형)과 **완전히 같은 공식**:
  · 이라스토야 고정 캐스트 재사용(신규 고유 0점 — 라이선스·브랜드 연속성)
  · 마스코트/범퍼/BGM 동일 자산
  · 실사는 이미 받아둔 Mixkit 클립만(네트워크 무의존)
  · 카드는 전면 타이포 → produce 시 --static 으로 전 씬 줌 OFF

실행: .venv/bin/python -m tracks.psychology.build_ep02
"""
from __future__ import annotations

from pathlib import Path

from tracks.psychology import cards, irasutoya

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data/assets/psychology/ep02"
CHIP = "사람 설명서"

# --- ep02 전용 캐스트 (ep01과 다른 일러스트 — 두 편이 똑같아 보이지 않게, 사용자 요청) ---
# 일본어 키워드로 검색해 ep01과 겹치지 않는 컷을 고르고, 슬러그는 e2_ 접두(_cast에서 부여)로
# ep01 캐시와 분리한다. 불안형 테마에 맞춰 골랐다(예: argue=폰에 화내는 사람, machi=폰 보다
# 잠든 여성). 15점 고유 = 무료 한도 20점 이내. (검수 규칙: 표정시트/문자/동물 컷 회피)
CAST: dict[str, tuple[str, str]] = {
    "worry":       ("不安", "女性"),          # 불안한 나
    "tired":       ("落ち込む", "女性"),      # 혼자 버티는(낙담)
    "argue":       ("文句", "スマート"),      # 폰에 대고 추궁("왜 답 안해")
    "counsel":     ("カウンセリング", ""),    # 털어놓기
    "idea":        ("メモ", "女性"),          # 정리·요약
    "machi":       ("スマホ", "女性"),        # 답장 기다리다 잠든
    "hanashiai":   ("仲直り", ""),            # 다시 대화·화해
    "fufu_kenka":  ("言い争い", ""),          # 말다툼
    "hagemasu":    ("手伝う", "仕事"),        # 먼저 도와주기
    "hakase":      ("研究者", "白衣"),        # 볼비·에인스워스(연구자)
    "naku_baby":   ("赤ちゃん", "泣く"),      # 우는 아기
    "dakko":       ("抱っこ", "赤ちゃん"),    # 안기는 아기(안정형)
    "shindenzu":   ("心拍", ""),              # 센서·심박
    "hitori":      ("落ち込む", "男性"),      # 물러선 사람(낙담 남성)
    "yorisou":     ("寄り添う", ""),          # 곁에 있어주기
}

MASCOT_SLUG = "mascot"

# --- 실사 클립 배치 (ep02 전용 생성 — 스톡 재사용 금지, 사용자 요청) ---------------
# 카드는 정보를, 실사는 감정을 나른다. 재사용 대신 이 스토리에 맞춘 실사를 GPT Image 2
# +Minimax i2v로 각각 생성한다: 불안하게 기다리는 여성 ↔ 태평하게 잠든 남친 같은 대비.
# 등장 여성은 훅/썸네일과 동일 인물(긴 머리·크림 니트)로 통일.
LIVE: dict[int, str] = {
    2:  "s02_sleeping_bf",     # 결론/대비 — 그것도 모르고 태평하게 잠든 남친
    19: "s19_window_wait",     # 매달림=생존기술 — 창가서 폰 끌어안고 기다리는 여성
    20: "s20_morning_calm",    # 당신은 부족하지 않다 — 아침빛, 숨 고르는 여성
    27: "s27_put_phone_down",  # 규칙성=보증서 — 안심하고 폰 내려놓는 여성
    33: "s33_reaching_away",   # 붙잡을수록 멀어진다 — 돌아서는 남자에게 손 뻗는 여성
    38: "s38_sunrise_hope",    # 다시 배울 수 있다 — 일출, 편안히 미소 짓는 여성
}
STOCK_DIR = ROOT / "data/assets/psychology/ep02_live"

# --- 씬 → 카드 매핑 (대본 40행과 1:1) ---------------------------------------
SCENES: list[tuple] = [
    ("focus", "machi",       "읽음 10분, 답장 없음", None),
    ("big",   "worry",       "당신은 집착하는 사람이 아닙니다", "", "결론부터"),
    ("focus", "mascot",      "오늘의 주제 · 불안형 애착", None),
    ("focus", "machi",       "답이 늦으면 최악을 상상한다", "01"),
    ("focus", "worry",       "표정·톤·마침표 하나까지 살핀다", "02"),
    ("focus", "tired",       "삐걱대면 아무것도 손에 안 잡힌다", "03"),
    ("big",   "idea",        "두 개 이상이면 불안형에 가깝습니다", "진단이 아니라, 이해를 위한 지도입니다", None),
    ("focus", "hakase",      "존 볼비 · 1950년대", None),
    ("big",   "naku_baby",   "애착 — 위험할 때 누군가에게 달려가는 본능", "이 본능이 응답받은 방식이 평생의 기본값이 된다", None),
    ("focus", "dakko",       "낯선 상황 실험 · 에인스워스", None),
    ("focus", "dakko",       "안정형 — 울고, 안기고, 다시 논다", None),
    ("focus", "naku_baby",   "불안형 — 안기면서 동시에 밀어낸다", None),
    ("focus", "shindenzu",   "그래서 몸에 센서를 붙였습니다", None),
    ("big",   "shindenzu",   "안겨서도 심장이 느려지지 않았습니다", "위로를 받는데도 경보는 꺼지지 않았다", "반전"),
    ("big",   "machi",       "스위치를 최대로 올린 것 — 과활성화 전략", "회피형이 스위치를 내렸다면, 불안형은 끝까지 올린다", None),
    ("big",   "machi",       "엄마를 좇던 아이가 서른 살에 읽음 표시를 확인합니다", "한 살 때의 그 경보기가 그대로 켜져 있다", None),
    ("big",   "worry",       "안심시키려는 말이 오히려 경보를 키웁니다", "지금부터가 오늘의 핵심입니다", None),
    ("focus", "hitori",      "어떤 날은 따뜻하고, 어떤 날은 차가웠다", None),
    ("big",   "hitori",      "매달림은 사랑 과잉이 아니라 오래된 생존 기술", "언제 사라질지 모른다는 불안에서 나온다", None),
    ("big",   "yorisou",     "당신은 부족한 사람이 아닙니다", "사랑이 예측 가능하게 돌아온다는 걸 배울 기회가 없었을 뿐", "혹시 본인이라면"),
    ("focus", "machi",       "상황 1 · 답 없는 10분", "01"),
    ("bad",   "argue",       "왜 답이 없어? 나한테 마음 식었어?"),
    ("good",  "machi",       "나 지금 회의 중이야. 여섯 시에 연락할게."),
    ("focus", "counsel",     "상황 2 · 확인하고 싶어질 때", "02"),
    ("bad",   "argue",       "그만 좀 물어봐. 지겨워."),
    ("good",  "yorisou",     "나 이따 자기 전에 전화할게."),
    ("big",   "machi",       "여섯 시라는 말이, 관계는 안 끝난다는 보증서가 됩니다", "안심은 크기보다 규칙성이다", None),
    ("big",   "mascot",      "세 번째가 관계를 가장 많이 흔듭니다", "구독해두시면 다음 편이 먼저 도착합니다", None),
    ("focus", "fufu_kenka",  "상황 3 · 시험하기", "03"),
    ("good",  "hanashiai",   "네가 밀어내도 나는 같은 자리에 있을게."),
    ("focus", "hagemasu",    "상황 4 · 직장에도 불안형이 있습니다", "04"),
    ("good",  "idea",        "짧은 답장은 사실, 나를 싫어한다는 건 상상."),
    ("big",   "fufu_kenka",  "붙잡을수록 멀어집니다", "불안형과 회피형이 만나면 생기는 추격과 도망의 굴레", "가장 잔인한 조합"),
    ("big",   "hanashiai",   "안정형은 감정이 아니라 약속으로 거리를 관리합니다", "굴레를 끊는 건 메시지를 쏟는 게 아니라 다음 시각을 정하는 것", None),
    ("list",  "mascot",      "오늘 쓸 수 있는 세 문장", [
        "언제 연락 가능한지 미리 알려줘",
        "보내기 전에 딱 90초만 기다리자",
        "밀어내는 대신, 나 지금 불안하다고 말하기",
    ]),
    ("big",   "hanashiai",   "세 문장 모두 침묵을 약속으로 바꿉니다", "필요한 건 더 많은 증거가 아니라 반복된 경험", None),
    ("big",   "machi",       "감정의 파도는 90초 — 그동안은 아무것도 보내지 않기", "후회는 대부분 그 90초 안에서 만들어진다", "불안형 본인이라면"),
    ("big",   "yorisou",     "배운 것은 다시 배울 수 있습니다", "후천적 안정 — 예측 가능하게 남아준 한 사람", None),
    ("big",   "counsel",     "이건 지도이지, 고치기 위한 설명서가 아닙니다", "불안이 일상을 무너뜨린다면 전문가와 이야기하세요", None),
    ("big",   "mascot",      "그 경보는 당신의 잘못이 아닙니다", "오늘 떠오른 그 사람은 어느 쪽이었나요", "댓글로 들려주세요"),
]


def _cast() -> dict[str, Path]:
    got: dict[str, Path] = {}
    for slug, (kw, prefer) in CAST.items():
        # e2_ 접두로 ep01 캐시(worry.png 등)와 분리 — 이미 받아둔 e2_*.png를 재사용
        p = irasutoya.fetch(kw, f"e2_{slug}", prefer=prefer)
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
    lines = (ROOT / "data/scripts/psy02_anxious.txt").read_text(encoding="utf-8").splitlines()
    n_lines = len([l for l in lines if l.strip()])
    if len(SCENES) != n_lines:
        raise SystemExit(f"씬 매핑 {len(SCENES)}개 ≠ 대본 {n_lines}행")

    print("1) 이라스토야 고정 캐스트 확보")
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

    print("3) 실사 클립 배치")
    import shutil

    for old in OUT.glob("*.mp4"):
        old.unlink()
    placed = 0
    for sid, clip in LIVE.items():
        src = STOCK_DIR / f"{clip}.mp4"
        if not src.exists():
            print(f"   ⚠ 씬 {sid}: 클립 {clip}.mp4 없음 — 카드로 대체됨")
            continue
        shutil.copy2(src, OUT / f"{sid}.mp4")
        placed += 1
    # 씬1 훅 = ep02 전용 새 여성(자체 i2v) — ep01 hook_woman 재사용 금지(같은 인물 중복).
    # 썸네일(kakao_gpt)과 동일 무드의 다른 여성. 미생성 시에만 ep01 소스로 폴백.
    hook = ROOT / "data/assets/psychology/character/hook_woman_ep02.mp4"
    if not hook.exists():
        hook = ROOT / "data/assets/psychology/character/hook_woman.mp4"
    if hook.exists():
        shutil.copy2(hook, OUT / "1.mp4")
        placed += 1
        print("   씬1 훅 → hook_woman_ep02.mp4")
    # 씬28 구독 CTA = 가나디 마스코트 애니(춤) — 정적 카드 대신 움직임으로 구독 유도(사용자 요청)
    cta = ROOT / "data/assets/psychology/character/mascot_cta.mp4"
    if cta.exists():
        shutil.copy2(cta, OUT / "28.mp4")
        placed += 1
        print("   씬28 CTA → mascot_cta.mp4 (가나디 춤)")
    print(f"   실사/애니 {placed}씬 / 카드 {len(SCENES) - placed}씬")

    static = ",".join(str(i) for i in range(1, len(SCENES) + 1))
    print("\n다음 단계 (전 씬 --static):")
    print("  .venv/bin/python cli.py produce \\")
    print("    --script data/scripts/psy02_anxious.txt \\")
    print("    --title '매달릴수록 멀어진다 | 불안형 애착의 머릿속에서 벌어지는 일' \\")
    print(f"    --track psychology --images {OUT.relative_to(ROOT)} \\")
    print(f"    --static {static}")
    return OUT


if __name__ == "__main__":
    build()
