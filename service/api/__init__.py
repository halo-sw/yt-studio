"""FastAPI 라우터 (cards, scenes, review, agents, votes, logs). M2에서 구현.

review 라우터: statemachine.SelfReviewError → HTTP 403 (규칙 5-4).
cards 라우터: statemachine.ClaimLockError → HTTP 409.
"""
