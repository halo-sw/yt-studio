"""리캡 트랙 — 냐옹체 스타일 린터 + 유튜브 가이드라인 치환.

업로드된 스타일 프롬프트(plans/12 §0)의 정량 스펙을 코드로 강제한다.
script.py의 lint_conte와 같은 원칙: 위반은 qc 실패가 아니라
부분 재생성(규칙 5-2) 대상 씬 지정에 쓴다. 단, 가이드라인 치환은
자동 교정한다 — '민감 표현 제외'는 사람 판단에 맡기지 않는다.
"""

from __future__ import annotations

import re

from core.schemas import Scene

# ---------------------------------------------------------------------------
# 유튜브 가이드라인 치환표 (샘플 프롬프트 원문 그대로)
# ---------------------------------------------------------------------------

GUIDELINE_SUBSTITUTIONS: dict[str, str] = {
    "살해했다": "제거했다",
    "살해": "제거",
    "자살": "스스로 떠남",
    "마약": "이상한 약",
    "고문했다": "괴롭혔다",
    "고문": "괴롭힘",
    "섹시한": "매력적인",
    "시체": "쓰러진 사람",
    "죽였다": "보내버렸다",
    "죽었다": "세상을 떠났다",
}

# 원본 충실성 — 관객/시청자 반응 언급 절대 금지 (냐옹체 핵심 원칙 1)
AUDIENCE_REFERENCES = ("관객", "시청자", "보는 사람들", "사람들이 놀랐", "사람들이 웃")


def apply_guideline_substitutions(text: str) -> str:
    """민감 표현을 자동 치환한다 (긴 표현 우선 매칭)."""
    for src in sorted(GUIDELINE_SUBSTITUTIONS, key=len, reverse=True):
        text = text.replace(src, GUIDELINE_SUBSTITUTIONS[src])
    return text


# ---------------------------------------------------------------------------
# 연결어 분포 (샘플 스펙: 는데 40 / 고 25 / 자 15 / 죠 10 / 습니다 5)
# ---------------------------------------------------------------------------

# 절 단위 어미 패턴 — 냐옹체는 연결어마다 행을 바꾸므로 행 단위로도 검사 가능
_ENDING_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("는데", re.compile(r"[는은]데[\s,.]|[는은]데$")),
    ("고", re.compile(r"[했랐갔왔넸됐졌섰컸팠았었였쳤뒀줬쐈]고[\s,.]|[했랐갔왔넸됐졌섰컸팠았었였쳤뒀줬쐈]고$")),
    ("자", re.compile(r"[하보이가오지치서니리키드]자[\s,.]|[하보이가오지치서니리키드]자$")),
    ("죠", re.compile(r"[죠쬬][\s,.!?]|[죠쬬]$")),
    ("습니다", re.compile(r"습니다|ㅂ니다")),
]

# 허용 범위 (스펙 ± 오차 — 생성 모델의 자연스러움을 위한 완충)
_DISTRIBUTION_RANGES = {
    "는데": (0.25, 0.55),
    "고": (0.10, 0.40),
    "자": (0.05, 0.30),
    "죠": (0.03, 0.25),
    "습니다": (0.00, 0.15),
}


def _clauses(text: str) -> list[str]:
    """문장/절 분해 — 행 변경 규칙 전이라면 문장부호 기준으로도 나눈다."""
    parts = re.split(r"[\n.!?]+", text)
    return [p.strip() for p in parts if p.strip()]


def _ending_of(clause: str) -> str | None:
    tail = clause[-12:] if len(clause) > 12 else clause
    for name, pat in _ENDING_PATTERNS:
        if pat.search(tail):
            return name
    return None


def ending_distribution(scenes: list[Scene]) -> dict[str, float]:
    """전체 내레이션의 연결어 분포 (분류된 절 기준 비율)."""
    counts: dict[str, int] = {name: 0 for name, _ in _ENDING_PATTERNS}
    total = 0
    for s in scenes:
        for clause in _clauses(s.narration):
            e = _ending_of(clause)
            if e:
                counts[e] += 1
                total += 1
    if total == 0:
        return {name: 0.0 for name in counts}
    return {name: c / total for name, c in counts.items()}


def lint_nyaong(scenes: list[Scene]) -> list[str]:
    """냐옹체 정량 규칙 검사. 반환된 이슈의 씬은 부분 재생성 대상."""
    issues: list[str] = []

    # 1) 원본 충실성 — 관객 언급 금지 (씬 단위)
    for s in scenes:
        for ref in AUDIENCE_REFERENCES:
            if ref in s.narration or ref in s.caption:
                issues.append(f"scene {s.scene_id}: 관객 반응 언급 금지 위반 — {ref!r}")

    # 2) 가이드라인 민감 표현 잔존 검사 (치환 후에는 남아 있으면 안 됨)
    for s in scenes:
        for banned in GUIDELINE_SUBSTITUTIONS:
            if banned in s.narration:
                issues.append(
                    f"scene {s.scene_id}: 민감 표현 {banned!r} 잔존 — "
                    f"apply_guideline_substitutions 미적용"
                )

    # 3) 연결어 분포 (에피소드 전체)
    dist = ending_distribution(scenes)
    for name, (lo, hi) in _DISTRIBUTION_RANGES.items():
        if not (lo <= dist[name] <= hi):
            issues.append(
                f"연결어 분포 위반: {name} {dist[name]:.0%} (허용 {lo:.0%}~{hi:.0%})"
            )

    # 4) 같은 연결어 3연속 금지 (에피소드 전체 절 시퀀스 기준)
    seq: list[tuple[int, str]] = []
    for s in scenes:
        for clause in _clauses(s.narration):
            e = _ending_of(clause)
            if e:
                seq.append((s.scene_id, e))
    for i in range(2, len(seq)):
        if seq[i][1] == seq[i - 1][1] == seq[i - 2][1]:
            issues.append(
                f"scene {seq[i][0]}: 연결어 {seq[i][1]!r} 3연속 — 리듬 위반"
            )

    # 5) 반말 검사 (존댓말 고정) — 절 끝이 반말 종결어미면 위반
    banmal = re.compile(r"(했다|였다|았다|간다|온다|이다)$")
    for s in scenes:
        for clause in _clauses(s.narration):
            if banmal.search(clause):
                issues.append(f"scene {s.scene_id}: 반말 종결 — {clause[-10:]!r}")
                break

    return issues
