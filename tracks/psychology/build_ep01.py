"""심리 B형 1편 「읽씹은 미움이 아니다 — 회피형 애착」 카드 빌더.

대본: data/scripts/psy01_avoidant.txt (40행 = 40씬, 5,508자 ≈ 10.6분 @8.67자/초)
출력: data/assets/psychology/ep01/{1..40}.png → cli.py produce --images 로 주입

라이선스: 이라스토야는 하나의 제작물에 **고유 21점부터 유료**(중복은 1점 카운트).
아래 CAST는 17점 고정 — 40씬 전체가 이 17점을 재사용한다. 재사용은 라이선스
여유이자 채널 브랜딩(같은 캐릭터가 계속 등장하는 시트콤 효과)이다.
malto편에서 받아둔 소재는 슬러그가 같으면 재다운로드 없이 캐시가 쓰인다.

렌더 주의: 카드는 화면 가장자리까지 타이포가 들어간 전면 디자인이므로
Ken Burns 줌을 걸면 글자가 잘린다. produce 시 --static 으로 전 씬 줌을 끈다.

실행: .venv/bin/python -m tracks.psychology.build_ep01
"""
from __future__ import annotations

from pathlib import Path

from tracks.psychology import cards, irasutoya

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data/assets/psychology/ep01"
CHIP = "사람 설명서"

# --- 고정 캐스트 (고유 17점) -------------------------------------------------
# slug -> (검색 키워드, 제목 우선 문자열). 일본어 검색은 공백을 넣으면 결과가
# 0이 되므로 키워드는 단일 토큰. ★ = malto편 캐시 재사용(네트워크 호출 없음).
#
# ⚠ 소재 검수 규칙 (malto편 + 본편에서 두 번 겪음 — 새 캐스트마다 반드시 육안 확인):
#   ① 일본어 글자가 그려진 컷 금지 (예: 「よろしくお願いします」) — 한국어 채널이다
#   ② '표정 모음 시트'류 금지 — 인물 여럿이 격자로 늘어선 컷은 단일 컷이 아니다
#   ③ 키워드가 뜻대로 안 걸림 — スイッチ는 난로, 質問은 직무질문이 1위로 온다
CAST: dict[str, tuple[str, str]] = {
    "worry":       ("悩む", ""),                  # ★ 상처받은 나
    "tired":       ("疲れた", ""),                # ★ 혼자 버티는 사람
    "argue":       ("怒る", ""),                  # ★ 추궁하는 쪽
    "counsel":     ("相談", ""),                  # ★ 털어놓기
    "idea":        ("ひらめき", ""),              # ★ 정리·요약
    "machi":       ("待つ", "スマホに夢中"),      # 답장을 기다리는 사람 (읽씹)
    "mimi":        ("耳をふさぐ", "男性"),        # 비활성화 전략 — 귀를 막는다
    "hanashiai":   ("話し合う", "話し合う人たちのイラスト（女性）"),  # 다시 대화
    "fufu_kenka":  ("夫婦喧嘩", "夫婦喧嘩のイラスト"),               # 말다툼
    "hagemasu":    ("励ます", "男性会社員"),      # 직장에서 먼저 다가가기
    "hakase":      ("顕微鏡", "研究"),            # 볼비·에인스워스 (연구자)
    "naku_baby":   ("泣く", "赤ちゃん"),          # 우는 아기
    "dakko":       ("抱っこ", "母親"),            # 안기는 아기 (안정형)
    "hitori_baby": ("積み木", "男の子"),          # 혼자 노는 아기 (회피형)
    "shindenzu":   ("心電図", ""),                # 센서·심박 측정
    "hitori":      ("体育座り", "後ろ姿"),        # 등을 돌리고 물러선 사람
    "yorisou":     ("慰める", "母親"),            # 곁에 있어주기
}

# 채널 마스코트는 이라스토야가 아니라 **자체 자산**이다 —
# 범퍼·썸네일에 쓰는 마스코트와 본편 마스코트가 다르면 강아지가 두 마리가 된다.
# 채널명이 마스코트에서 나온 이상 여기서 어긋나면 브랜딩이 무너진다.
# (이라스토야 고유 점수에도 안 잡히므로 라이선스 여유가 오히려 늘어난다.)
MASCOT_SLUG = "mascot"

# --- 실사 클립 배치 --------------------------------------------------------
# 카드만 40씬 이어지면 10분이 단조롭다(malto편도 실사 스톡을 섞었다).
# 원칙: **카드는 정보를, 실사는 감정을 나른다.**
#   이론·실험·✕✓ 대사 = 카드 (정보 밀도가 필요)
#   훅·고독·위로·희망    = 실사 (문장으로 안 되는 걸 화면이 한다)
# 9/40씬(22%)만 실사 — 더 늘리면 카드 아이덴티티가 흐려진다.
# 소재: Mixkit 무료 라이선스(상업 이용 가능, 크레딧 표기 불요).
# produce는 같은 씬 번호에 영상이 있으면 영상을 우선하므로 png는 그대로 둔다.
LIVE: dict[int, str] = {
    1:  "47985",   # 훅 — 무표정하게 답장을 기다리는 사람
    2:  "35426",   # 훅 — 해질녘 난간에 기대 먼 곳을 보는 실루엣
                   #      (22240 커튼 여는 컷은 동작이 밝아 "정반대입니다"와 톤 충돌)
    18: "46448",   # 울어도 아무도 오지 않았을 때 — 무릎 안고 앉은 사람
    19: "35830",   # 거리 두기는 생존 기술 — 혼자 먼 길을 걸어가는 뒷모습
    20: "46788",   # 당신은 차가운 사람이 아닙니다 — 밤길, 온기
    24: "12837",   # 갈등 중 침묵 — 벤치에 혼자 앉은 사람
    27: "20311",   # 아홉 시라는 보증서 — 빗방울 맺힌 창(기다림)
    33: "35889",   # 다가갈수록 물러섭니다 — 바다에 혼자 선 사람
    38: "6104",    # 배운 것은 다시 배울 수 있습니다 — 일출
}
STOCK_DIR = ROOT / "data/assets/psychology/stockvideo"

# --- 씬 → 카드 매핑 (대본 40행과 1:1) ---------------------------------------
# ("focus", 일러스트, 헤드라인|None, 넘버|None)
# ("big",   일러스트, 헤드라인, 서브, 액센트|None)
# ("bad"/"good", 일러스트, 대사)              → quote_frame (✕ / ✓ 말풍선)
# ("list",  일러스트, 제목, [항목...])
SCENES: list[tuple] = [
    ("focus", "machi",       "읽음 3분, 답장 없음", None),
    ("big",   "worry",       "그 사람은 당신이 싫어서 답장을 안 한 게 아닙니다", "", "결론부터"),
    ("focus", "mascot",      "오늘의 주제 · 회피형 애착", None),
    ("focus", "argue",       "갈등이 생기면 조용해진다", "01"),
    ("focus", "hitori",      "가까워질 때쯤 멀어진다", "02"),
    ("focus", "tired",       "힘든 일을 말하지 않는다", "03"),
    ("big",   "idea",        "두 개 이상이면 회피형에 가깝습니다", "진단이 아니라, 이해를 위한 지도입니다", None),
    ("focus", "hakase",      "존 볼비 · 1950년대", None),
    ("big",   "naku_baby",   "애착 — 위험할 때 누군가에게 달려가는 본능", "이 본능이 다뤄진 방식이 평생의 기본값이 된다", None),
    ("focus", "dakko",       "낯선 상황 실험 · 에인스워스", None),
    ("focus", "dakko",       "안정형 — 울고, 안기고, 다시 논다", None),
    ("focus", "hitori_baby", "회피형 — 울지 않는다", None),
    ("focus", "shindenzu",   "그래서 몸에 센서를 붙였습니다", None),
    ("big",   "shindenzu",   "울지 않던 아기의 심장이 더 빨리 뛰고 있었습니다", "손엔 땀, 스트레스 호르몬은 더 오래 남았다", "반전"),
    ("big",   "mimi",      "덜 느끼는 게 아니라, 스위치를 내린 것", "심리학 용어로 — 비활성화 전략", None),
    ("big",   "machi",       "한 살의 그 아이가 서른 살에 휴대폰을 엎어놓습니다", "어른의 연애에서도 거의 그대로 반복된다", None),
    ("big",   "worry",       "우리가 건네는 말이 그 스위치를 더 누릅니다", "지금부터가 오늘의 핵심입니다", None),
    ("focus", "naku_baby",   "울어도 아무도 오지 않았을 때", None),
    ("big",   "hitori",      "거리 두기는 무관심이 아니라 오래된 생존 기술", "가장 가까워지고 싶은 사람 앞에서 가장 먼저 켜진다", None),
    ("big",   "yorisou",     "당신은 차가운 사람이 아닙니다", "안전하게 가까워지는 법을 배울 기회가 없었을 뿐입니다", "혹시 본인이라면"),
    ("focus", "machi",       "상황 1 · 읽씹", "01"),
    ("bad",   "argue",       "읽었으면서 왜 답을 안 해?"),
    ("good",  "machi",       "지금 어려우면 내일도 괜찮아. 언제쯤 가능한지만 알려줘."),
    ("focus", "fufu_kenka",       "상황 2 · 갈등 중 침묵", "02"),
    ("bad",   "fufu_kenka",       "말을 해야 알 거 아냐. 오늘 안에 끝내자."),
    ("good",  "hanashiai",        "삼십 분만 각자 있다가, 아홉 시에 다시 얘기하자."),
    ("big",   "hanashiai",        "아홉 시라는 말이, 관계는 안 끝난다는 보증서가 됩니다", "보증서가 지켜지면 도망가는 거리가 짧아진다", None),
    ("big",   "mascot",      "세 번째가 가장 많이 어긋납니다", "구독해두시면 다음 편이 먼저 도착합니다", None),
    ("focus", "counsel",     "상황 3 · 왜 말 안 했어", "03"),
    ("good",  "yorisou",     "말하기 싫으면 안 해도 돼. 대신 내가 옆에 있을게."),
    ("focus", "hagemasu",         "상황 4 · 직장에도 회피형이 있습니다", "04"),
    ("good",  "hagemasu",         "이거 삼십 분만 같이 볼까요?"),
    ("big",   "fufu_kenka",       "다가갈수록 물러섭니다", "불안형과 회피형이 만나면 생기는 추격과 도망의 굴레", "가장 잔인한 조합"),
    ("big",   "hanashiai",        "안정형은 감정이 아니라 약속으로 거리를 관리합니다", "굴레를 끊는 건 추격을 멈추는 게 아니라 다음 시각을 정하는 것", None),
    ("list",  "mascot",      "오늘 쓸 수 있는 세 문장", [
        "언제쯤 가능한지만 알려줘",
        "삼십 분 뒤 아홉 시에 다시 얘기하자",
        "말 안 해도 되니까 옆에 있을게",
    ]),
    ("big",   "hanashiai",        "세 문장 모두 출구와 시간을 함께 줍니다", "문이 열려 있는데도 돌아오는 경험", None),
    ("big",   "machi",       "사라지기 전에, 사라진다고 말하기", "스위치를 억지로 올릴 필요는 없습니다. 내려간다고 알려주면 됩니다", "회피형 본인이라면"),
    ("big",   "yorisou",     "배운 것은 다시 배울 수 있습니다", "후천적 안정 — 예측 가능하게 곁에 있어준 한 사람", None),
    ("big",   "counsel",     "이건 지도이지, 고치기 위한 설명서가 아닙니다", "내 마음이 먼저 꺼지고 있다면 전문가와 이야기하세요", None),
    ("big",   "mascot",      "다음 편 · 불안형", "답장이 삼 분만 늦어도 심장이 내려앉는 사람", "댓글로 알려주세요"),
]


def _cast() -> dict[str, Path]:
    """캐스트 확보. 이미 캐시된 소재는 네트워크 호출 없이 재사용된다."""
    got: dict[str, Path] = {}
    for slug, (kw, prefer) in CAST.items():
        p = irasutoya.fetch(kw, slug, prefer=prefer)
        if p:
            got[slug] = p
        else:
            print(f"   ⚠ 캐스트 누락: {slug} ({kw}) — 키워드 재지정 필요")
    limit = irasutoya.FREE_LIMIT_PER_VIDEO
    n = len(got)
    print(f"   이라스토야 {n}/{len(CAST)}점 (무료 한도 {limit}점, 여유 {limit - n}점)")
    if n > limit:
        raise SystemExit(f"고유 소재 {n}점 — 무료 한도 {limit}점 초과. 캐스트를 줄일 것")

    # 신규 파스텔 마스코트(그라디언트 브랜드) — 배지·본문 일러스트 통일 (2026-07-26)
    new_mascot = ROOT / "data/assets/psychology/character/mascot_cut.png"
    from tracks.psychology.brand import mascot_cutout
    got[MASCOT_SLUG] = new_mascot if new_mascot.exists() else mascot_cutout()
    print(f"   마스코트 → {got[MASCOT_SLUG].name}")
    return got


def build() -> Path:
    lines = (ROOT / "data/scripts/psy01_avoidant.txt").read_text(encoding="utf-8").splitlines()
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
    # 씬1 훅 = 예쁜 20대 한국 여성(자체 생성 i2v) — 스톡 여성보다 강한 첫인상
    # (2026-07-26 사용자 요청). LIVE[1] 스톡 클립을 덮어쓴다.
    hook = ROOT / "data/assets/psychology/character/hook_woman.mp4"
    if hook.exists():
        shutil.copy2(hook, OUT / "1.mp4")
        print("   씬1 훅 → hook_woman.mp4 (예쁜 20대 한국 여성)")
    print(f"   실사 {placed}씬 / 카드 {len(SCENES) - placed}씬")

    static = ",".join(str(i) for i in range(1, len(SCENES) + 1))
    print("\n다음 단계 (카드는 전면 타이포라 Ken Burns 금지 → 전 씬 --static):")
    print("  .venv/bin/python cli.py produce \\")
    print("    --script data/scripts/psy01_avoidant.txt \\")
    print("    --title '읽씹은 미움이 아니다 | 회피형 애착의 머릿속에서 벌어지는 일' \\")
    print(f"    --track psychology --images {OUT.relative_to(ROOT)} \\")
    print(f"    --static {static} --shorts")
    return OUT


if __name__ == "__main__":
    build()
