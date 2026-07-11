"""core/publish.py — 제목 3안·설명·localizations 생성, 예약 업로드. M3에서 구현.

- 규칙 5-6: YouTube API 감사(audit) 통과 전까지 "예약 초안 업로드 →
  사람이 공개 전환" 하이브리드. publish 후 상태 verify 필수
  (EpisodeModel.publish_verified 기록).
- 채널별 OAuth 토큰은 data/tokens/ (커밋 금지).
"""
