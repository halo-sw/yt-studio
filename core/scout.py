"""core/scout.py — 경쟁 채널 폴링(YouTube API), 아웃라이어 감지, 소재 카드 생성.

M3에서 구현. 산출물은 core.schemas.Card (state=draft, owner/approved_by 없음).
사람 게이트 1(소재 확정) 전에는 파이프라인이 진행되지 않는다 (statemachine 강제).
"""
