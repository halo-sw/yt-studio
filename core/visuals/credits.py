"""Higgsfield 크레딧 예상·실측 (규칙 5-8 관제).

왜 필요한가 — CLI가 **작업별 크레딧을 응답에 안 싣고**, 이력도 최근 20건만
남는다. 그래서 나중에 "이 채널에 얼마 썼나"를 물으면 파일 개수로 역산하는
수밖에 없고, 실패·재시도로 태운 크레딧은 아예 집계에서 빠진다.

해법 두 겹:
  ① **예상 차감** — 생성 직전에 단가표로 계산해 알린다 (네트워크 호출 없음)
  ② **실측 차감** — 배치 전후 잔액 차이로 확인하고 원장에 남긴다

원장: data/usage/higgsfield.jsonl (한 줄 = 한 작업)

단가는 CLAUDE.md 11장 실측표 기준. 새 모델을 쓰면 여기에 먼저 추가할 것 —
표에 없으면 예상이 `?`로 나오고, 그건 "얼마 나갈지 모르는 채로 태우는 중"이라는
경고다.
"""
from __future__ import annotations

import json
import re
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HF_BIN = str(Path.home() / ".local/bin/higgsfield")
LEDGER = ROOT / "data/usage/higgsfield.jsonl"

# 모델 → 단가. 영상은 초당 단가로 환산해 duration에 비례시킨다.
#   image: {해상도: 크레딧}   (None = 기본값)
#   video: {"per_sec": 초당, "ref": "기준 길이 기준가"}
UNIT: dict[str, dict] = {
    # --- 이미지 (CLAUDE.md 11장 실측) ---
    "gpt_image_2":         {"kind": "image", "1k": 4.0, "2k": 7.0, None: 4.0},
    "nano_banana_2":       {"kind": "image", None: 2.0},
    "nano_banana_2_lite":  {"kind": "image", None: 1.0},
    "z_image":             {"kind": "image", None: 0.15},
    # --- 영상 ---
    "minimax_hailuo":      {"kind": "video", "per_sec": 6.0 / 6},    # 6cr / 6s
    "kling3_0_turbo":      {"kind": "video", "per_sec": 7.5 / 5},    # 7.5cr / 5s
    "seedance_2_0":        {"kind": "video", "per_sec": 22.5 / 5},   # 22.5cr / 5s
}

# 단가 미확인 모델 — 태우기 전에 사람이 확인하라는 뜻으로 명시적으로 남긴다.
UNKNOWN_NOTE = "단가 미확인 — CLAUDE.md 단가표에 추가 필요"


def estimate(model: str, *, resolution: str | None = None,
             duration: float | None = None, n: int = 1) -> float | None:
    """예상 차감 크레딧. 표에 없는 모델은 None(=모름)."""
    spec = UNIT.get(model)
    if not spec:
        return None
    if spec["kind"] == "image":
        base = spec.get(resolution, spec.get(None))
    else:
        base = spec["per_sec"] * float(duration if duration is not None else 5)
    return None if base is None else round(base * n, 2)


def fmt(cr: float | None) -> str:
    return f"{cr:g}cr" if cr is not None else f"?cr ({UNKNOWN_NOTE})"


def balance() -> float | None:
    """현재 잔액. CLI 미설치·미인증이면 None."""
    try:
        r = subprocess.run([HF_BIN, "account", "status"],
                           capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return None
    m = re.search(r"([\d.]+)\s*credits", r.stdout)
    return float(m.group(1)) if m else None


def record(model: str, *, label: str = "", track: str = "",
           estimated: float | None = None, ok: bool = True,
           balance_before: float | None = None,
           balance_after: float | None = None) -> None:
    """원장 한 줄. 실패한 작업도 남긴다 — 실패가 크레딧을 안 태웠다는 보장이 없다."""
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "track": track, "label": label, "model": model,
        "estimated": estimated, "ok": ok,
        "balance_before": balance_before, "balance_after": balance_after,
        "actual": (round(balance_before - balance_after, 2)
                   if balance_before is not None and balance_after is not None
                   else None),
    }
    with LEDGER.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


class Batch:
    """배치 단위 실측. 작업마다 잔액을 조회하면 느리므로 앞뒤로 한 번씩만 잰다.

        with Batch("sijang 7편 비주얼", track="natepan") as b:
            ...  # gen_image / gen_motion 호출
        # 종료 시 예상 합계 vs 실제 차감을 대조해 출력
    """

    def __init__(self, label: str, track: str = ""):
        self.label, self.track = label, track
        self.planned = 0.0
        self.unknown = 0
        self.before: float | None = None

    def __enter__(self) -> "Batch":
        self.before = balance()
        b = f"{self.before:g}cr" if self.before is not None else "조회 실패"
        print(f"[크레딧] '{self.label}' 시작 — 잔액 {b}", flush=True)
        return self

    def add(self, cr: float | None) -> None:
        if cr is None:
            self.unknown += 1
        else:
            self.planned += cr

    def __exit__(self, *exc) -> None:
        after = balance()
        parts = [f"예상 {self.planned:g}cr"]
        if self.unknown:
            parts.append(f"+ 단가미상 {self.unknown}건")
        if self.before is not None and after is not None:
            parts.append(f"실제 {self.before - after:g}cr")
            parts.append(f"잔액 {after:g}cr")
        print(f"[크레딧] '{self.label}' 종료 — " + " · ".join(parts), flush=True)
        record("(batch)", label=self.label, track=self.track,
               estimated=round(self.planned, 2),
               balance_before=self.before, balance_after=after)


_ACTIVE: Batch | None = None


def active() -> Batch | None:
    return _ACTIVE


def set_active(b: Batch | None) -> None:
    global _ACTIVE
    _ACTIVE = b
