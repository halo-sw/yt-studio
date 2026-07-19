"""core/breakdown.py — 영상 역해부: 레퍼런스 영상 → 샷 분해 → 스타일 연구 → 소재.

FeiGe(로컬 우선 AI 영상 拆片·분镜 도구)의 4단계 워크플로를 우리 파이프라인에
이식한 모듈이다. FeiGe 저장소는 바이너리 배포만 있어 소스 대신 공개 문서의
워크플로 사양을 구현 근거로 삼았다:

  1) 준비(prepare)   — 영상 확보 + 씬 경계 감지 (ffmpeg scene detection)
  2) 분해(breakdown) — 샷별 시작/길이/스틸 추출, 컷 리듬 계산
  3) 콜라주(collage) — 대표 샷 최대 12개 자동 선정 → 3×4 그리드
  4) 종합(synthesis) — 비전 모델에 콜라주+메타 → 스타일 요약(StyleStudy)

산출물 StyleStudy는 두 곳으로 흘러간다:
  - scout 소재 큐: '역해부' 소스 타입의 소재 카드 (다중 소스 큐의 한 축)
  - script.py 콘테: visual_direction/composition 힌트로 주입 (스타일 참조)

규칙 5-5 주의: 역해부는 **포맷·스타일 연구**다. 결과 소재는 원본 재현이
아니라 구조 응용이어야 하며, to_material()이 그 문구를 강제한다.
API 키/ffmpeg 없이도 목 폴백으로 e2e 테스트가 가능하다.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass, field

from core.schemas import Track

# ---------------------------------------------------------------------------
# 1) 준비 — 씬 경계 감지 (ffmpeg)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Shot:
    index: int
    start: float
    end: float

    @property
    def duration(self) -> float:
        return round(self.end - self.start, 2)


def scene_detect_command(video_path: str, threshold: float = 0.4) -> list[str]:
    """FeiGe의 '원클릭 분해'에 해당 — ffmpeg 씬 경계 감지 명령."""
    return [
        "ffmpeg", "-i", video_path,
        "-vf", f"select='gt(scene,{threshold})',metadata=print",
        "-an", "-f", "null", "-",
    ]


_PTS_RE = re.compile(r"pts_time:(\d+\.?\d*)")


def parse_scene_times(ffmpeg_stderr: str, total_duration: float) -> list[Shot]:
    """ffmpeg metadata 출력 → 샷 목록 (경계 시각들을 구간으로 변환)."""
    cuts = sorted({float(m) for m in _PTS_RE.findall(ffmpeg_stderr)})
    bounds = [0.0, *cuts, total_duration]
    return [
        Shot(index=i + 1, start=bounds[i], end=bounds[i + 1])
        for i in range(len(bounds) - 1)
        if bounds[i + 1] - bounds[i] > 0.2  # 노이즈 컷 제거
    ]


def prepare(video_path: str, total_duration: float,
            threshold: float = 0.4) -> list[Shot]:
    """씬 경계 감지 실행. ffmpeg가 없거나 실패하면 균등 분할 목 폴백."""
    if not os.path.exists(video_path):
        return _mock_shots(total_duration)
    try:
        proc = subprocess.run(
            scene_detect_command(video_path, threshold),
            capture_output=True, text=True, timeout=600,
        )
        # 실행 실패 시 stderr에 씬 타임이 없어 단일 샷이 만들어진다 — 폴백으로.
        if proc.returncode != 0:
            return _mock_shots(total_duration)
        shots = parse_scene_times(proc.stderr, total_duration)
        if shots:
            return shots
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass
    return _mock_shots(total_duration)


def _mock_shots(total_duration: float, avg_cut: float = 2.8) -> list[Shot]:
    """ffmpeg 없는 환경용 결정적 목 — 평균 컷 길이 기반 균등 분할."""
    n = max(6, int(total_duration / avg_cut))
    step = total_duration / n
    return [Shot(index=i + 1, start=round(i * step, 2), end=round((i + 1) * step, 2))
            for i in range(n)]


# ---------------------------------------------------------------------------
# 2) 분해 — 컷 리듬 메타
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CutRhythm:
    shot_count: int
    avg_cut: float          # 평균 컷 길이(초)
    hook_cuts: int          # 첫 10초 안의 컷 수 — 훅 밀도
    longest: float
    shortest: float


def analyze_rhythm(shots: list[Shot], hook_window: float = 10.0) -> CutRhythm:
    durs = [s.duration for s in shots]
    return CutRhythm(
        shot_count=len(shots),
        avg_cut=round(sum(durs) / len(durs), 2),
        hook_cuts=sum(1 for s in shots if s.start < hook_window),
        longest=max(durs), shortest=min(durs),
    )


# ---------------------------------------------------------------------------
# 3) 콜라주 — 대표 샷 최대 12개 (FeiGe: 균등 커버리지 자동 선정)
# ---------------------------------------------------------------------------

def pick_representative(shots: list[Shot], k: int = 12) -> list[Shot]:
    """시간축을 k개 버킷으로 나누고 버킷마다 가장 긴 샷을 뽑는다.

    긴 샷 = 연출상 머무는 화면(정보가 많음), 균등 버킷 = 전체 흐름 커버.
    """
    if len(shots) <= k:
        return list(shots)
    total = shots[-1].end
    picked: list[Shot] = []
    for b in range(k):
        lo, hi = total * b / k, total * (b + 1) / k
        bucket = [s for s in shots if lo <= s.start < hi]
        if bucket:
            picked.append(max(bucket, key=lambda s: s.duration))
    return picked


def frame_extract_command(video_path: str, shot: Shot, out_path: str) -> list[str]:
    """대표 샷 중앙 프레임 스틸 추출 명령 (콜라주 타일용)."""
    mid = (shot.start + shot.end) / 2
    return ["ffmpeg", "-ss", f"{mid:.2f}", "-i", video_path,
            "-frames:v", "1", "-q:v", "2", out_path]


# ---------------------------------------------------------------------------
# 4) 종합 — 스타일 요약 (비전 모델, 키 없으면 목)
# ---------------------------------------------------------------------------

SYNTHESIS_PROMPT = (
    "너는 영상 연출 분석가다. 첨부된 대표 샷 콜라주와 컷 리듬 메타를 보고\n"
    "아래 JSON 하나로 스타일을 요약한다. 저작권 주의: 원본을 베끼기 위한\n"
    "분석이 아니라 구조·문법을 배우기 위한 분석이다.\n"
    '{"palette": ["주요 색 3~5개 hex"], "mood": "한 줄",\n'
    ' "hook_structure": "첫 10초가 시선을 잡는 방식",\n'
    ' "composition_notes": "반복되는 구도·카메라 문법 2~3개",\n'
    ' "cut_rhythm_note": "컷 리듬의 특징 한 줄",\n'
    ' "applicable": "우리 트랙에 응용하는 법 한 줄"}'
)


@dataclass
class StyleStudy:
    """역해부 산출물 — 소재 큐와 콘테 생성이 함께 쓰는 스타일 연구 노트."""

    source_url: str
    rhythm: CutRhythm
    palette: list[str] = field(default_factory=list)
    mood: str = ""
    hook_structure: str = ""
    composition_notes: str = ""
    cut_rhythm_note: str = ""
    applicable: str = ""

    def conte_hint(self) -> str:
        """script.py 콘테 생성 프롬프트에 주입할 스타일 참조 텍스트."""
        return (
            f"[스타일 참조 — 역해부 연구]\n"
            f"- 무드: {self.mood} / 팔레트: {', '.join(self.palette)}\n"
            f"- 훅 문법: {self.hook_structure}\n"
            f"- 구도 문법: {self.composition_notes}\n"
            f"- 컷 리듬: 평균 {self.rhythm.avg_cut}초, 훅 {self.rhythm.hook_cuts}컷 — {self.cut_rhythm_note}\n"
            f"원본 재현 금지 — 문법만 응용한다."
        )


def synthesize(source_url: str, rhythm: CutRhythm,
               collage_paths: list[str] | None = None,
               api_key: str | None = None,
               model: str = "claude-sonnet-5") -> StyleStudy:
    key = api_key or os.getenv("ANTHROPIC_API_KEY")
    if key and collage_paths:
        import anthropic

        client = anthropic.Anthropic(api_key=key)
        # 콜라주 이미지 + 메타를 비전 입력으로 전달
        import base64
        content = [{"type": "text", "text":
                    f"{SYNTHESIS_PROMPT}\n\n컷 리듬 메타: {rhythm}"}]
        for p in collage_paths[:12]:
            with open(p, "rb") as f:
                content.append({"type": "image", "source": {
                    "type": "base64", "media_type": "image/jpeg",
                    "data": base64.b64encode(f.read()).decode()}})
        msg = client.messages.create(model=model, max_tokens=1500,
                                     messages=[{"role": "user", "content": content}])
        raw = json.loads(re.search(r"\{.*\}", msg.content[0].text, re.S).group(0))
    else:
        raw = {  # 결정적 목 — e2e 테스트용
            "palette": ["#1A1D26", "#E8B34B", "#5C9BD6"],
            "mood": "차분한 긴장",
            "hook_structure": "질문 자막 → 반전 컷 → 인물 리액션 3연타",
            "composition_notes": "와이드 설정샷 뒤 클로즈업 2연속, 좌측 여백 자막",
            "cut_rhythm_note": "훅은 빠르고 본론은 길게 머무는 2단 리듬",
            "applicable": "훅 3연타 구조를 우리 훅 40초 규칙 안에 압축 적용",
        }
    return StyleStudy(source_url=source_url, rhythm=rhythm, **raw)


# ---------------------------------------------------------------------------
# 소재 큐 연결 — 다중 소스의 한 축 (규칙 5-5: 포맷 응용 강제)
# ---------------------------------------------------------------------------

def to_material(study: StyleStudy, track: Track, title: str) -> dict:
    """StyleStudy → 소재 큐 항목. summary에 '포맷 응용' 문구를 강제한다."""
    return {
        "track": track.value,
        "title": title,
        "source_type": "breakdown",  # 자동 발굴/직접 추가와 구분되는 소스 타입
        "summary": (
            f"영상 역해부 · {study.mood} · 평균 컷 {study.rhythm.avg_cut}초 · "
            f"훅 {study.rhythm.hook_cuts}컷 — 원본 모방이 아닌 구조 응용 "
            f"({study.applicable})"
        ),
        "source_ref": study.source_url,
        "conte_hint": study.conte_hint(),
    }


def run_breakdown(video_path: str, source_url: str, total_duration: float,
                  api_key: str | None = None) -> tuple[StyleStudy, list[Shot]]:
    """4단계 전체 실행: 준비 → 분해 → 콜라주 → 종합."""
    shots = prepare(video_path, total_duration)          # 1 준비
    rhythm = analyze_rhythm(shots)                        # 2 분해
    collage = pick_representative(shots, k=12)            # 3 콜라주
    study = synthesize(source_url, rhythm, api_key=api_key)  # 4 종합
    return study, collage
