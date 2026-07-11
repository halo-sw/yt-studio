"""core/tts.py — ElevenLabs 씬별 mp3 생성 + ffprobe 길이 실측. M1에서 구현.

- 바이블의 voice_id/voice_params 사용 (잠금 자산).
- 생성 후 ffprobe로 실측한 길이를 Scene.duration에 기입.
- ELEVENLABS_API_KEY 없으면 espeak-ng 폴백 (M1 프롬프트 2 요구사항).
- 규칙 5-8: 사용 문자수를 UsageLogModel에 기록 (재생성은 is_regen=True).
"""
