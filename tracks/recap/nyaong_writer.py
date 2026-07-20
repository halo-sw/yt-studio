"""리캡 트랙 — 냐옹체 작가: 원본 이벤트 시퀀스 → 씬 JSON.

입력은 source_ingest가 만든 원본 이벤트 시퀀스(시간순 사건 목록)와 샷
타임라인이다. 출력 씬은 기존 스키마 그대로 — visual.type=clip,
visual.ref="원본 시작초-끝초" (assemble.preset_recap이 해석).

원본 충실성(냐옹체 원칙 1)의 구현: 작가는 이벤트 시퀀스에 있는 사건만
쓸 수 있다. 시퀀스는 라이선스 게이트를 통과한 원본에서만 나온다(규칙 5-5).
ANTHROPIC_API_KEY 없으면 결정적 목 폴백 (파이프라인 e2e 원칙).
"""

from __future__ import annotations

import os

from core.breakdown import Shot
from core.schemas import Bible, Conte, Emotion, Scene, SceneContext, SceneVisual, Track
from core.script import parse_scenes
from tracks.recap.style_lint import apply_guideline_substitutions

# 업로드된 스타일 프롬프트의 핵심 압축본 — 시스템 프롬프트로 주입
NYAONG_SYSTEM_PROMPT = """너는 영상 리캡 채널의 작가다. 아래 냐옹체 규칙을 엄격히 따른다.

[원본 충실성 — 최우선]
- 제공된 이벤트 시퀀스에 있는 사건만 쓴다. 캐릭터·반응·상황 창작 절대 금지.
- "관객", "시청자", "보는 사람들" 등 시청자 반응 언급 절대 금지.
- 등장인물의 행동과 감정만 서술하고, 모든 중요 사건을 시간순으로 빠짐없이 포함한다.

[문체]
- 존댓말 고정. 내면 묘사 최소화, 눈에 보이는 행동만 빠르게. 한 문장에 행동 2~3개 연결.
- 연결어 분포: ~했는데 40% / ~했고 25% / ~하자 15% / ~했죠 10% / ~했습니다 5%.
- 같은 연결어 3연속 금지. 연결어마다 씬(행)을 나눈다.
- 유머는 전체의 5~10%만.

[유튜브 가이드라인 — 치환 필수]
- 죽었다→세상을 떠났다, 살해→제거, 시체→쓰러진 사람, 자살→스스로 떠남,
  마약→이상한 약, 고문→괴롭힘, 섹시한→매력적인.

[출력]
- 씬 = 내레이션 절 1~2개 + 원본 샷 참조. visual.type은 "clip",
  visual.ref는 반드시 제공된 샷 목록의 "시작-끝" 초 표기를 그대로 쓴다."""


def _shot_ref(shot: Shot) -> str:
    return f"{shot.start:.2f}-{shot.end:.2f}"


def build_user_prompt(events: list[str], shots: list[Shot], title: str) -> str:
    shot_list = "\n".join(f"  - {_shot_ref(s)}" for s in shots)
    event_list = "\n".join(f"  {i + 1}. {e}" for i, e in enumerate(events))
    return (
        f"원본 제목: {title}\n\n"
        f"[이벤트 시퀀스 — 이 사건만, 이 순서대로]\n{event_list}\n\n"
        f"[사용 가능한 원본 샷 (visual.ref에 그대로 사용)]\n{shot_list}\n\n"
        f"씬 JSON 배열로만 출력한다."
    )


# ---------------------------------------------------------------------------
# 결정적 목 — 연결어 분포 스펙(40/25/15/10/5)을 만족하는 어미 사이클
# ---------------------------------------------------------------------------

# 20절 주기: 는데 8(40%) / 고 5(25%) / 자 3(15%) / 죠 2(10%) / 습니다 1(5%) + 는데 1
_MOCK_ENDINGS = [
    "이어졌는데", "상황이 급해졌고", "몸을 던지자", "위기를 넘겼죠",
    "일이 커졌는데", "빠르게 움직였고", "문이 열렸는데", "결단을 내렸습니다",
    "반전이 있었는데", "그대로 달렸고", "뒤를 돌아보자", "정체가 드러났죠",
    "분위기가 변했는데", "손을 뻗었고", "신호가 오자", "모든 게 멈췄는데",
    "끝이 보였는데", "마지막 힘을 냈고", "숨을 고르자", "이야기가 정리됐는데",
]


def _mock_scenes(
    events: list[str], shots: list[Shot], track: Track = Track.RECAP
) -> list[Scene]:
    scenes: list[Scene] = []
    for i, event in enumerate(events):
        shot = shots[i % len(shots)]
        e1 = _MOCK_ENDINGS[(i * 2) % len(_MOCK_ENDINGS)]
        e2 = _MOCK_ENDINGS[(i * 2 + 1) % len(_MOCK_ENDINGS)]
        narration = apply_guideline_substitutions(
            f"{event} 그렇게 흐름이 {e1}\n다음 순간 {e2}"
        )
        scenes.append(Scene(
            scene_id=i + 1, track=track, chapter="리캡",
            narration=narration, caption=event[:30],
            visual=SceneVisual(type="clip", ref=_shot_ref(shot), effect="none"),
            conte=Conte(
                info_point=event[:40],
                emotion=Emotion(tone="텐션 유지", delivery="빠르게, 연결어 앞 반 박자 쉼"),
                composition="원본 샷 그대로, 하단 자막 여백",
                visual_direction=f"원본 {_shot_ref(shot)} 구간 컷",
            ),
        ))
    return scenes


def write_recap(
    events: list[str],
    shots: list[Shot],
    bible: Bible,
    title: str = "",
    api_key: str | None = None,
    model: str = "claude-sonnet-5",
) -> list[Scene]:
    """이벤트 시퀀스 → 냐옹체 씬 목록. 키 없으면 결정적 목."""
    if not events:
        raise ValueError("이벤트 시퀀스가 비어 있음 — source_ingest부터")
    if not shots:
        raise ValueError("샷 타임라인 없음 — source_ingest.ingest_source부터")

    key = api_key or os.getenv("ANTHROPIC_API_KEY")
    if key:
        import anthropic

        client = anthropic.Anthropic(api_key=key)
        banned = ", ".join(bible.banned_phrases)
        msg = client.messages.create(
            model=model, max_tokens=16_000,
            system=f"{NYAONG_SYSTEM_PROMPT}\n\n[채널 금지어]: {banned}",
            messages=[{"role": "user", "content": build_user_prompt(events, shots, title)}],
        )
        scenes = parse_scenes(msg.content[0].text, Track.RECAP)
        for s in scenes:
            s.narration = apply_guideline_substitutions(s.narration)
            s.caption = apply_guideline_substitutions(s.caption)
    else:
        scenes = _mock_scenes(events, shots)

    # 규칙 5-2 대비: prev_tail/next_head 문맥 기입
    for i, s in enumerate(scenes):
        s.context = SceneContext(
            prev_tail=scenes[i - 1].narration.splitlines()[-1] if i > 0 else "",
            next_head=scenes[i + 1].narration.splitlines()[0] if i < len(scenes) - 1 else "",
        )
    return scenes
