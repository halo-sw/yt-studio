"""core/assemble.py — FFmpeg 조립. M1(playlist_1h, longform_16x9)에서 구현.

프리셋 3종 + 씬 교체(replace_scene).
- 규칙 5-1 오디오 2트랙: 내레이션·효과음=씬 레이어(-14 LUFS),
  BGM=에피소드 글로벌 트랙(-26 LUFS 언더베드, 최종 믹스에서 합성).
  씬 교체 시 BGM은 건드리지 않는다.
- 규칙 5-2 부분 재생성: replace_scene은 씬 경계 50~100ms 크로스페이드로
  이어붙인다. 전체 재렌더로 부분 수정을 대체하지 않는다 (CLAUDE.md 10장).
"""
