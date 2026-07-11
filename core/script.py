"""core/script.py — 대본 생성: 트랙별 시스템 프롬프트 조립 + Claude API → 씬 JSON v1.

여기가 "만들기 시작"이 실제로 하는 일의 1단계다. 프롬프트는 코드로 조립되며,
아래 절대 규칙이 프롬프트 텍스트에 문자 그대로 들어간다:

- 규칙 5-7 길이 제어: 10분 = 씬 26~32개 = 3,300~3,600자(일어 3,500자),
  훅 40초 내, 미드롤(4/7/10분) 직전 클리프행어.
- 규칙 5-3 사실 시트: 수치는 {{fact:key}} 토큰으로만 출력.
- 규칙 5-5 저작권: 트랙별 금지 사항(드라마썰 비평 의무, 네이트판 재창작 등).
- 규칙 5-2 부분 재생성: 바이블 잠금 자산 + prev_tail/next_head 자동 주입.

ANTHROPIC_API_KEY가 없으면 결정적 목 생성기로 폴백해 파이프라인 e2e 테스트가
가능하다 (M1 프롬프트 2의 espeak-ng 폴백과 같은 원칙).
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field

from core.schemas import Bible, Manifest, Scene, SceneContext, SceneVisual, Track

# ---------------------------------------------------------------------------
# 규칙 5-7 — 길이 제어 스펙 (10분 기준을 분 단위로 스케일)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LengthSpec:
    minutes: int
    min_scenes: int
    max_scenes: int
    min_chars: int
    max_chars: int
    hook_seconds: int = 40                    # 훅은 40초 내
    midrolls: tuple[int, ...] = (240, 420, 600)  # 4/7/10분 — 직전 클리프행어

    @classmethod
    def for_minutes(cls, minutes: int, track: Track) -> "LengthSpec":
        scale = minutes / 10
        # 일어(일본 머니) 3,500자 기준, 그 외 3,300~3,600자 (규칙 5-7)
        if track is Track.JAPAN:
            base_min, base_max = 3_400, 3_600
        else:
            base_min, base_max = 3_300, 3_600
        return cls(
            minutes=minutes,
            min_scenes=round(26 * scale),
            max_scenes=round(32 * scale),
            min_chars=round(base_min * scale),
            max_chars=round(base_max * scale),
            midrolls=tuple(s for s in (240, 420, 600) if s < minutes * 60),
        )


# ---------------------------------------------------------------------------
# 트랙별 페르소나·규칙 프롬프트 (규칙 5-5 반영)
# ---------------------------------------------------------------------------

TRACK_PROMPTS: dict[Track, str] = {
    Track.JAPAN: (
        "너는 일본 경제·머니 채널의 작가다. 톤: 차분한 다큐멘터리, 데이터 근거 중심.\n"
        "- 투자 권유·단정적 전망 표현 금지 (감수 2인 게이트가 다시 검사한다).\n"
        "- 일본 고유명사는 용어집 표기를 그대로 따른다."
    ),
    Track.REALESTATE: (
        "너는 부동산 분석 채널의 작가다. 톤: 건조하고 정확하게, 숫자는 비교로 보여준다.\n"
        "- 시세 전망을 단정하지 않는다. '지금이 바닥' 류 표현 금지.\n"
        "- 모든 수치(시세·평수·금액)는 반드시 사실 시트 토큰으로만 쓴다."
    ),
    Track.DRAMA: (
        "너는 드라마 비평 채널의 작가다. 톤: 텐션 있는 썰 + 반드시 씬마다 해석/비평.\n"
        "- 저작권 규칙(절대): 줄거리 서술은 전체 분량의 30%를 넘지 않는다. 각 씬은\n"
        "  줄거리 요약이 아니라 '왜 그 장면이 작동하는가'라는 비평이 중심이다.\n"
        "- 배우 실명·작품 스틸컷 참조 금지. 인물은 창작 외형(인물 카드)으로만 지칭."
    ),
    Track.NATEPAN: (
        "너는 사연 채널의 작가다. 톤: 담담한 낭독, 감정 과잉 금지.\n"
        "- 저작권 규칙(절대): 특정 원문 각색이 아니라 복수 사연의 모티프를 결합한\n"
        "  재창작이어야 한다. 원문 문장 재사용·실명/닉네임 노출 금지."
    ),
    Track.PLAYLIST: (
        "너는 음악 플레이리스트 채널의 큐레이터다. 내레이션은 오프닝 큐레이션 노트\n"
        "1~2씬만 쓰고, 나머지는 곡 소개 캡션 위주로 최소화한다."
    ),
}


# ---------------------------------------------------------------------------
# 프롬프트 조립 — "만들기 시작"이 실제로 보내는 내용
# ---------------------------------------------------------------------------

SCENE_JSON_SPEC = (
    '각 씬은 다음 JSON으로 출력한다:\n'
    '{"scene_id": int, "chapter": str, "narration": str, "caption": str,\n'
    ' "visual": {"type": "slide|chart|doc_highlight|illust|clip|loop_art",'
    ' "ref": "생성 프롬프트 또는 에셋 힌트", "effect": "kenburns|zoom_callout|none"}}\n'
    "전체 출력은 씬 객체의 JSON 배열 하나여야 한다. 배열 밖 텍스트 금지."
)


def build_system_prompt(track: Track, bible: Bible, spec: LengthSpec) -> str:
    """트랙 페르소나 + 바이블 잠금 자산 + 절대 규칙을 시스템 프롬프트로 조립."""
    glossary = "\n".join(f"  - {k} → {v}" for k, v in bible.glossary.items()) or "  (없음)"
    banned = ", ".join(bible.banned_phrases) or "(없음)"
    midroll_txt = ", ".join(f"{s // 60}분" for s in spec.midrolls)
    return (
        f"{TRACK_PROMPTS[track]}\n\n"
        f"[채널 바이블 — 잠금 자산, 위반 금지]\n"
        f"용어집(이 표기만 사용):\n{glossary}\n"
        f"금지어: {banned}\n\n"
        f"[길이 제어 — 규칙 5-7]\n"
        f"- 목표 {spec.minutes}분: 씬 {spec.min_scenes}~{spec.max_scenes}개, "
        f"내레이션 합계 {spec.min_chars:,}~{spec.max_chars:,}자.\n"
        f"- 훅(1~2씬)은 {spec.hook_seconds}초 안에 끝나는 분량으로.\n"
        f"- 미드롤 지점({midroll_txt}) 직전 씬은 클리프행어로 끝낸다.\n\n"
        f"[사실 시트 — 규칙 5-3, 절대]\n"
        f"- 수치·연도·금액·퍼센트는 절대 직접 쓰지 않는다. 반드시 {{{{fact:키이름}}}}\n"
        f"  토큰으로만 쓴다. 예: '평균 연봉은 {{{{fact:jp_avg_salary}}}}엔'.\n"
        f"- 필요한 fact 키 목록을 마지막 씬 뒤에 별도로 나열하지 말고 토큰으로만 남긴다.\n\n"
        f"[출력 형식]\n{SCENE_JSON_SPEC}"
    )


def build_user_prompt(manifest: Manifest) -> str:
    chapters = " / ".join(manifest.chapters) or "훅 / 본론 / 마무리"
    cast = ""
    if manifest.cast_cards:
        cast = "\n[인물 카드 — 외형 잠금, 이 묘사로만 지칭]\n" + "\n".join(
            f"  - {c.name}: {c.appearance}" for c in manifest.cast_cards
        )
    return (
        f"주제(아웃라인): {manifest.outline}\n"
        f"챕터 구성: {chapters}{cast}\n"
        f"사용 가능한 fact 키: {', '.join(manifest.fact_sheet.facts) or '(스카우트가 채움)'}"
    )


def build_regen_prompt(scene: Scene, bible: Bible, manifest: Manifest) -> str:
    """규칙 5-2: 씬 1개 재생성 — 잠금 자산 + 앞뒤 문맥 자동 주입.

    이 함수가 regen_scene 잡의 프롬프트 원본이다. 전체 재생성 경로는 없다.
    """
    return (
        f"다음 씬 하나만 다시 쓴다. 다른 씬은 절대 건드리지 않는다.\n\n"
        f"[앞 씬의 끝 문장 — 억양·문맥을 여기에 자연스럽게 잇는다]\n"
        f"{scene.context.prev_tail or '(첫 씬)'}\n\n"
        f"[뒷 씬의 첫 문장 — 이 문장으로 자연스럽게 넘어가야 한다]\n"
        f"{scene.context.next_head or '(마지막 씬)'}\n\n"
        f"[기존 씬]\n{scene.model_dump_json(exclude={'duration'})}\n\n"
        f"[금지어]: {', '.join(bible.banned_phrases) or '(없음)'}\n"
        f"[fact 키]: {', '.join(manifest.fact_sheet.facts)}\n"
        f"수치는 {{{{fact:키}}}} 토큰으로만. 같은 scene_id·chapter를 유지한 씬 JSON\n"
        f"객체 하나만 출력한다."
    )


def prompt_summary(track: Track, bible: Bible, spec: LengthSpec) -> dict:
    """UI 노출용 요약 — '이 버튼이 실제로 보내는 프롬프트' 확인 패널의 데이터."""
    return {
        "track_persona": TRACK_PROMPTS[track].splitlines()[0],
        "glossary_terms": len(bible.glossary),
        "banned_phrases": list(bible.banned_phrases),
        "scenes": f"{spec.min_scenes}~{spec.max_scenes}개",
        "chars": f"{spec.min_chars:,}~{spec.max_chars:,}자",
        "hook": f"{spec.hook_seconds}초 내",
        "midroll_cliffhangers": [f"{s // 60}분" for s in spec.midrolls],
        "fact_rule": "수치는 {{fact:key}} 토큰만 허용",
    }


# ---------------------------------------------------------------------------
# 생성 실행 (Claude API, 키 없으면 결정적 목 폴백)
# ---------------------------------------------------------------------------

@dataclass
class LengthReport:
    """규칙 5-7 검증 결과. ok가 아니면 reinforce_chapters에 보강 씬을 요청한다."""

    scene_count: int
    total_chars: int
    ok: bool
    issues: list[str] = field(default_factory=list)
    reinforce_chapters: list[str] = field(default_factory=list)


def validate_length(scenes: list[Scene], spec: LengthSpec) -> LengthReport:
    total = sum(len(s.narration) for s in scenes)
    issues: list[str] = []
    reinforce: list[str] = []
    if len(scenes) < spec.min_scenes:
        issues.append(f"씬 {len(scenes)}개 < 최소 {spec.min_scenes}개")
    if total < spec.min_chars:
        issues.append(f"내레이션 {total:,}자 < 최소 {spec.min_chars:,}자")
        # 가장 분량이 적은 챕터부터 보강 요청 (규칙 5-7: 지정 챕터 보강 씬)
        by_chapter: dict[str, int] = {}
        for s in scenes:
            by_chapter[s.chapter] = by_chapter.get(s.chapter, 0) + len(s.narration)
        reinforce = sorted(by_chapter, key=by_chapter.get)[:2]
    if total > spec.max_chars:
        issues.append(f"내레이션 {total:,}자 > 최대 {spec.max_chars:,}자")
    return LengthReport(
        scene_count=len(scenes), total_chars=total,
        ok=not issues, issues=issues, reinforce_chapters=reinforce,
    )


_NUMERIC_PATTERN = re.compile(r"(?<!\{)\b\d{4,}\b|\d+\s*[%％]|\d+(억|만)\s*원|\d+\s*엔")


def lint_fact_rule(scenes: list[Scene]) -> list[str]:
    """규칙 5-3 린트: 토큰 밖에 굵직한 수치가 남아 있으면 경고 (qc.py 사전 검사)."""
    hits = []
    for s in scenes:
        stripped = re.sub(r"\{\{fact:[^}]+\}\}", "", s.narration)
        if _NUMERIC_PATTERN.search(stripped):
            hits.append(f"scene {s.scene_id}: 사실 시트 토큰 밖 수치 의심")
    return hits


def _attach_context(scenes: list[Scene]) -> list[Scene]:
    """규칙 5-2: 각 씬에 prev_tail/next_head를 기입해 재생성 대비."""
    for i, s in enumerate(scenes):
        prev_tail = scenes[i - 1].narration.split(".")[-2].strip() + "." if i > 0 and "." in scenes[i - 1].narration else (scenes[i - 1].narration if i > 0 else "")
        next_head = scenes[i + 1].narration.split(".")[0].strip() + "." if i < len(scenes) - 1 and "." in scenes[i + 1].narration else (scenes[i + 1].narration if i < len(scenes) - 1 else "")
        s.context = SceneContext(prev_tail=prev_tail, next_head=next_head)
    return scenes


def parse_scenes(raw: str, track: Track) -> list[Scene]:
    """모델 출력(JSON 배열)을 Scene 목록으로 검증 파싱."""
    m = re.search(r"\[.*\]", raw, re.S)
    if not m:
        raise ValueError("씬 JSON 배열을 찾지 못함")
    items = json.loads(m.group(0))
    scenes = [
        Scene(
            scene_id=it["scene_id"], track=track, chapter=it["chapter"],
            narration=it["narration"], caption=it.get("caption", ""),
            visual=SceneVisual(**it["visual"]),
        )
        for it in items
    ]
    return _attach_context(scenes)


def _mock_scenes(manifest: Manifest, spec: LengthSpec) -> list[Scene]:
    """API 키 없이 파이프라인 e2e를 돌리기 위한 결정적 목 생성기."""
    chapters = manifest.chapters or ["훅", "본론 1", "본론 2", "마무리"]
    n = spec.min_scenes
    per_scene = max(spec.min_chars // n + 1, 60)
    fact_keys = list(manifest.fact_sheet.facts) or ["sample_metric"]
    scenes = []
    for i in range(n):
        chapter = chapters[min(i * len(chapters) // n, len(chapters) - 1)]
        fact = fact_keys[i % len(fact_keys)]
        base = (
            f"{manifest.outline}에 대한 {chapter} 파트 {i + 1}번째 이야기입니다. "
            f"핵심 수치는 {{{{fact:{fact}}}}}입니다. "
        )
        filler = "이 흐름이 다음 장면으로 이어집니다. "
        narration = (base + filler * ((per_scene - len(base)) // len(filler) + 1))[:per_scene]
        scenes.append(Scene(
            scene_id=i + 1, track=manifest.track, chapter=chapter,
            narration=narration, caption=f"{chapter} · {i + 1}",
            visual=SceneVisual(type="slide", ref=f"mock/scene_{i + 1}", effect="kenburns"),
        ))
    return _attach_context(scenes)


def generate_script(
    manifest: Manifest, bible: Bible, minutes: int = 10,
    api_key: str | None = None, model: str = "claude-sonnet-5",
) -> tuple[list[Scene], LengthReport]:
    """대본 생성 진입점 — service/workers의 generate 잡이 호출한다.

    반환된 LengthReport.ok가 False면 워커가 reinforce_chapters로 보강 씬을
    재요청한다 (규칙 5-7).
    """
    spec = LengthSpec.for_minutes(minutes, manifest.track)
    key = api_key or os.getenv("ANTHROPIC_API_KEY")
    if key:
        import anthropic

        client = anthropic.Anthropic(api_key=key)
        msg = client.messages.create(
            model=model, max_tokens=16_000,
            system=build_system_prompt(manifest.track, bible, spec),
            messages=[{"role": "user", "content": build_user_prompt(manifest)}],
        )
        scenes = parse_scenes(msg.content[0].text, manifest.track)
    else:
        scenes = _mock_scenes(manifest, spec)
    return scenes, validate_length(scenes, spec)
