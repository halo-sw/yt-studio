"""core/tts.py — ElevenLabs 씬별 mp3 생성 + ffprobe 길이 실측.

- 바이블의 voice_id/voice_params 사용 (잠금 자산 — 규칙 5-2: 재생성 시에도
  같은 보이스가 자동 주입되어 톤 일관성을 보장한다).
- 생성 후 ffprobe로 실측한 길이를 Scene.duration에 기입 (규칙 5-7 길이
  제어의 근거 데이터 — TTS 실측 합산 후 미달 시 보강 씬 요청).
- ELEVENLABS_API_KEY 없으면 espeak-ng 폴백 (M1 프롬프트 2 요구사항) —
  키 없이도 파이프라인 e2e가 끝까지 돈다.
- 규칙 5-3: 내레이션의 {{fact:key}} 토큰은 렌더(=합성) 직전에 fact_sheet로
  치환한다. 시트에 없는 키는 즉시 실패 — 수치 누락 영상이 나가는 것을 막는다.
- 규칙 5-8: 사용 문자수를 UsageLogModel에 기록 (재생성은 is_regen=True).
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from core.schemas import FACT_REF_PATTERN, Bible, FactSheet, Scene

ELEVENLABS_TTS_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
TYPECAST_API_BASE = "https://api.typecast.ai/v1"
TYPECAST_MODEL = "ssfm-v21"

# espeak-ng 기본 낭독 속도(wpm). 바이블 voice_params.speed를 곱해 쓴다.
_ESPEAK_BASE_WPM = 165

# 트랙별 espeak 보이스 (폴백 전용 — 실서비스 보이스는 바이블 voice_id).
_ESPEAK_VOICE_BY_LANG = {"japan": "ko", "default": "ko"}


class TTSError(RuntimeError):
    pass


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise TTSError(f"명령 실패: {' '.join(cmd[:3])}…\n{proc.stderr[-800:]}")
    return proc


def probe_duration(path: str | Path) -> float:
    """ffprobe로 오디오 길이를 실측한다 (규칙 5-7: 추정치 금지, 실측만)."""
    proc = _run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "csv=p=0", str(path),
    ])
    return float(proc.stdout.strip())


def resolve_fact_tokens(text: str, fact_sheet: FactSheet) -> str:
    """{{fact:key}} → 실제 값 치환 (규칙 5-3: 렌더 직전 치환의 구현 지점).

    시트에 없는 키는 TTSError — 빈 수치로 영상이 나가는 것보다 실패가 낫다.
    """

    def _sub(m):
        key = m.group(1)
        if key not in fact_sheet.facts:
            raise TTSError(f"fact_sheet에 없는 키: {key} (규칙 5-3 위반)")
        value = fact_sheet.facts[key]
        return f"{value:,}" if isinstance(value, int) else str(value)

    return FACT_REF_PATTERN.sub(_sub, text)


# ---------------------------------------------------------------------------
# 합성 백엔드
# ---------------------------------------------------------------------------

def _synthesize_elevenlabs(
    text: str, bible: Bible, out_path: Path, api_key: str
) -> Path:
    """ElevenLabs REST 호출 — 바이블 잠금 보이스로만 합성한다."""
    import requests

    resp = requests.post(
        ELEVENLABS_TTS_URL.format(voice_id=bible.voice_id),
        headers={"xi-api-key": api_key, "Content-Type": "application/json"},
        json={
            "text": text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {
                "stability": bible.voice_params.stability,
                "similarity_boost": bible.voice_params.similarity,
                "speed": bible.voice_params.speed,
            },
        },
        timeout=120,
    )
    if resp.status_code != 200:
        raise TTSError(f"ElevenLabs {resp.status_code}: {resp.text[:300]}")
    out_path.write_bytes(resp.content)
    return out_path


def list_typecast_voices(api_key: str) -> list[dict]:
    """타입캐스트 보이스 목록 — 바이블 voice_id 확정용."""
    import requests

    resp = requests.get(
        f"{TYPECAST_API_BASE}/voices",
        headers={"X-API-KEY": api_key},
        params={"model": TYPECAST_MODEL},
        timeout=30,
    )
    if resp.status_code != 200:
        raise TTSError(f"Typecast voices {resp.status_code}: {resp.text[:300]}")
    return resp.json()


def _synthesize_typecast(
    text: str, bible: Bible, out_path: Path, api_key: str
) -> Path:
    """타입캐스트 REST 호출. 바이블 voice_id가 미확정(TODO_*)이면
    보이스 목록의 첫 한국어 보이스로 자동 선택하고 로그를 남긴다."""
    import requests

    voice_id = bible.voice_id
    if voice_id.startswith("TODO"):
        voices = list_typecast_voices(api_key)
        if not voices:
            raise TTSError("Typecast 보이스 목록이 비어 있음")
        voice_id = voices[0].get("voice_id") or voices[0].get("id", "")
        print(f"   [tts] 바이블 voice_id 미확정 → Typecast 자동 선택: {voice_id} "
              f"({voices[0].get('voice_name', '?')}) — data/bibles에 확정 기입 권장")

    resp = requests.post(
        f"{TYPECAST_API_BASE}/text-to-speech",
        headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
        json={
            "voice_id": voice_id,
            "text": text,
            "model": TYPECAST_MODEL,
            "language": "kor",
            "output": {
                "audio_format": "wav",
                "audio_tempo": bible.voice_params.speed,
            },
        },
        timeout=120,
    )
    if resp.status_code != 200:
        raise TTSError(f"Typecast {resp.status_code}: {resp.text[:300]}")
    wav_path = out_path.with_suffix(".wav")
    wav_path.write_bytes(resp.content)
    return wav_path


def _synthesize_espeak(text: str, bible: Bible, out_path: Path) -> Path:
    """espeak-ng 폴백 — 키 없이 e2e를 돌리기 위한 로컬 합성.

    바이블 voice_params.speed만 반영한다(espeak가 지원하는 유일한 공통 파라미터).
    """
    if shutil.which("espeak-ng") is None:
        raise TTSError("espeak-ng 미설치 — ELEVENLABS_API_KEY도 없어 합성 불가")
    voice = _ESPEAK_VOICE_BY_LANG.get(bible.channel.value, _ESPEAK_VOICE_BY_LANG["default"])
    wpm = round(_ESPEAK_BASE_WPM * bible.voice_params.speed)
    wav_path = out_path.with_suffix(".wav")
    _run(["espeak-ng", "-v", voice, "-s", str(wpm), "-w", str(wav_path), text])
    return wav_path


# ---------------------------------------------------------------------------
# 씬/에피소드 단위 진입점
# ---------------------------------------------------------------------------

@dataclass
class SceneAudio:
    scene_id: int
    path: Path
    duration: float
    chars: int          # 규칙 5-8: 사용량 집계 단위(문자수)
    backend: str        # "elevenlabs" | "espeak"


def synthesize_scene(
    scene: Scene,
    bible: Bible,
    fact_sheet: FactSheet,
    out_dir: str | Path,
    *,
    api_key: str | None = None,
    is_regen: bool = False,
    session=None,
    episode_id: str | None = None,
) -> SceneAudio:
    """씬 하나를 합성하고 duration을 실측해 scene.duration에 기입한다.

    부분 재생성(규칙 5-2)도 이 함수를 그대로 쓴다 — is_regen=True로 호출해
    재생성 크레딧을 별도 집계(규칙 5-8)할 뿐, 경로는 동일하다.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    text = resolve_fact_tokens(scene.narration, fact_sheet)

    # 백엔드 우선순위: Typecast > ElevenLabs > espeak-ng 폴백.
    # 상위 백엔드가 네트워크 차단·키 오류로 실패하면 경고 후 다음으로 폴백한다
    # — 발행 파이프라인이 외부 장애로 멈추지 않게 (규칙 5-8 정신).
    tc_key = os.getenv("TYPECAST_API_KEY")
    el_key = api_key or os.getenv("ELEVENLABS_API_KEY")
    base = out_dir / f"scene_{scene.scene_id:03d}.mp3"
    path, backend = None, ""
    if tc_key:
        try:
            path = _synthesize_typecast(text, bible, base, tc_key)
            backend = "typecast"
        except Exception as e:  # 프록시 차단/키 오류 포함
            print(f"   [tts] Typecast 실패 → 폴백 ({type(e).__name__}: {str(e)[:100]})")
    if path is None and el_key:
        try:
            path = _synthesize_elevenlabs(text, bible, base, el_key)
            backend = "elevenlabs"
        except Exception as e:
            print(f"   [tts] ElevenLabs 실패 → 폴백 ({type(e).__name__}: {str(e)[:100]})")
    if path is None:
        path = _synthesize_espeak(text, bible, base)
        backend = "espeak"

    duration = probe_duration(path)
    scene.duration = duration  # 규칙 5-7: 실측값 기입

    if session is not None:
        from core.models import UsageLogModel

        session.add(UsageLogModel(
            service=backend, episode_id=episode_id,
            units=float(len(text)), is_regen=is_regen,
        ))
        session.commit()

    return SceneAudio(
        scene_id=scene.scene_id, path=path, duration=duration,
        chars=len(text), backend=backend,
    )


def synthesize_episode(
    scenes: list[Scene],
    bible: Bible,
    fact_sheet: FactSheet,
    out_dir: str | Path,
    *,
    api_key: str | None = None,
    session=None,
    episode_id: str | None = None,
) -> list[SceneAudio]:
    """에피소드 전체 합성. 반환 순서는 scene_id 순.

    합산 길이가 목표에 미달하면 script.validate_length가 보강 씬을 요청하는
    근거가 된다 (규칙 5-7) — 판단은 워커/CLI 몫, 여기서는 실측만 한다.
    """
    return [
        synthesize_scene(
            s, bible, fact_sheet, out_dir,
            api_key=api_key, session=session, episode_id=episode_id,
        )
        for s in sorted(scenes, key=lambda s: s.scene_id)
    ]


def total_duration(audios: list[SceneAudio]) -> float:
    return sum(a.duration for a in audios)
