"""플레이리스트 — 곡 DB (ingest + 조립 입력 변환).

규칙 5-5(절대): 라이선스 메타 없는 곡은 ingest 거부. 격리 계정 소재도 예외
없음 — license_meta가 None이면 LicenseError를 던지고 DB에 넣지 않는다.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from core.assemble import PlaylistTrackIn

REQUIRED_LICENSE_FIELDS = ("source", "license")  # 최소: 출처 + 라이선스 종류


class LicenseError(ValueError):
    pass


@dataclass
class Song:
    path: str
    title: str
    artist: str = ""
    license_meta: dict | None = None

    def validate_license(self) -> None:
        """규칙 5-5: 메타 없음/필수 필드 누락이면 즉시 거부."""
        if not self.license_meta:
            raise LicenseError(f"라이선스 메타 없는 곡 ingest 거부: {self.title}")
        missing = [f for f in REQUIRED_LICENSE_FIELDS if not self.license_meta.get(f)]
        if missing:
            raise LicenseError(f"{self.title}: 라이선스 필수 필드 누락 {missing}")
        if not Path(self.path).exists():
            raise LicenseError(f"{self.title}: 파일 없음 {self.path}")


def ingest(session, song: Song, episode_id: str | None = None):
    """곡을 AssetModel(kind='song')로 등록한다. 라이선스 검증 실패 시 미등록."""
    from core.models import AssetModel

    song.validate_license()
    asset = AssetModel(
        episode_id=episode_id, kind="song", path=song.path,
        license_meta=song.license_meta,
    )
    session.add(asset)
    session.commit()
    return asset


def to_assemble_inputs(songs: list[Song]) -> list[PlaylistTrackIn]:
    """검증된 곡 목록 → assemble.preset_playlist_1h 입력.

    조립 직전에 한 번 더 검증한다 — ingest를 우회한 경로도 여기서 걸린다.
    """
    for s in songs:
        s.validate_license()
    return [PlaylistTrackIn(path=s.path, title=s.title, artist=s.artist) for s in songs]
