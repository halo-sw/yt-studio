"""core/harvest.py — 24h/7d 지표 수집, 스카우트 가중치 피드백, 클레임 모니터.

M4에서 구현. published 에피소드의 지표를 수집해 scout 가중치에 반영하고,
저작권 클레임 발생을 모니터링해 관제 알림(TELEGRAM_BOT_TOKEN)으로 보낸다.
"""
