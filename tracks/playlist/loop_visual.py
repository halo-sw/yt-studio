"""플레이리스트 — 루프 비주얼 (loop_art).

M1은 core.assemble.make_placeholder_image 플레이스홀더 + preset_playlist_1h의
이미지/영상 루프 입력으로 충분하다. 실 루프 아트는 MJ/Higgsfield 수동
대기열(비주얼 대기열 화면, M2)에서 생성해 visual_path로 넘긴다.
"""

from core.assemble import make_placeholder_image

__all__ = ["make_placeholder_image"]
