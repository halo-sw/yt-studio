"""core/source_ingest.py — 리캡 원본 수집: 라이선스 게이트 + 샷 타임라인.

절대 규칙 5-5: 라이선스 메타 없는 원본은 ingest 거부 — 격리 계정 소재도
예외 없음. '민감 소재 제외'는 사람 기억이 아니라 이 게이트가 강제한다.

수집 경로:
- 로컬 파일 (제휴·자체 소재 전달본)
- URL (yt-dlp 설치 시) — 단, URL이어도 라이선스 메타는 반드시 사람이 확인해
  입력해야 한다. 자동으로 '허가됨'을 추정하지 않는다.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from core.breakdown import Shot, prepare
from core.tts import probe_duration

REQUIRED_LICENSE_FIELDS = ("source", "license", "permission_ref")
# permission_ref: 허가 근거 (CC 조항 URL, 제휴 계약 ID, 자체 제작 표기 등)


class SourceLicenseError(ValueError):
    pass


class SourceIngestError(RuntimeError):
    pass


@dataclass
class SourceMeta:
    source_id: str
    path: str
    title: str
    license_meta: dict
    duration: float
    shots: list[Shot] = field(default_factory=list)
    transcript: str = ""   # 자막/STT 텍스트 (이벤트 시퀀스 추출 입력)


def validate_license(title: str, license_meta: dict | None) -> None:
    """규칙 5-5 게이트. 실패 시 어떤 파일도 저장하지 않는다."""
    if not license_meta:
        raise SourceLicenseError(f"라이선스 메타 없는 원본 ingest 거부: {title}")
    missing = [f for f in REQUIRED_LICENSE_FIELDS if not license_meta.get(f)]
    if missing:
        raise SourceLicenseError(f"{title}: 라이선스 필수 필드 누락 {missing}")


def _download(url: str, out_dir: Path) -> Path:
    if shutil.which("yt-dlp") is None:
        raise SourceIngestError("yt-dlp 미설치 — URL 수집 불가, 로컬 파일로 전달하라")
    out_tpl = str(out_dir / "%(id)s.%(ext)s")
    proc = subprocess.run(
        ["yt-dlp", "-f", "mp4/best", "-o", out_tpl, "--no-playlist",
         "--print", "after_move:filepath", url],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        raise SourceIngestError(f"다운로드 실패: {proc.stderr[-400:]}")
    return Path(proc.stdout.strip().splitlines()[-1])


def ingest_source(
    path_or_url: str,
    title: str,
    license_meta: dict | None,
    workdir: str | Path,
    *,
    source_id: str | None = None,
    transcript: str = "",
    session=None,
    episode_id: str | None = None,
) -> SourceMeta:
    """원본 1건 수집: 라이선스 검증 → (다운로드) → 길이 실측 → 샷 감지.

    반환된 shots가 nyaong_writer의 visual.ref 후보, transcript가 이벤트
    시퀀스 추출 입력이 된다.
    """
    validate_license(title, license_meta)

    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    if path_or_url.startswith(("http://", "https://")):
        path = _download(path_or_url, workdir)
    else:
        path = Path(path_or_url)
        if not path.exists():
            raise SourceIngestError(f"원본 파일 없음: {path}")

    duration = probe_duration(path)
    shots = prepare(str(path), total_duration=duration)
    sid = source_id or path.stem

    if session is not None:
        from core.models import AssetModel

        session.add(AssetModel(
            episode_id=episode_id, kind="source_clip", path=str(path),
            license_meta=license_meta,
        ))
        session.commit()

    return SourceMeta(
        source_id=sid, path=str(path), title=title,
        license_meta=dict(license_meta or {}), duration=duration,
        shots=shots, transcript=transcript,
    )


def events_from_transcript(transcript: str, max_events: int = 24) -> list[str]:
    """자막/STT 텍스트 → 이벤트 시퀀스 초안 (문장 단위 분할).

    실서비스에서는 Claude로 사건 요약을 뽑지만, 키 없이도 파이프라인이
    돌도록 문장 분할 폴백을 기본 제공한다. 원본에 없는 사건이 생기지
    않는 가장 보수적인 방법이기도 하다 (원본 충실성).
    """
    import re

    sentences = [s.strip() for s in re.split(r"[.!?\n]+", transcript) if len(s.strip()) > 5]
    if len(sentences) <= max_events:
        return sentences
    step = len(sentences) / max_events
    return [sentences[int(i * step)] for i in range(max_events)]
