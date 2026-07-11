"""core/qc.py — 품질 검사. M4 고도화, 기본 검사는 M1~M2에서 점진 구현.

- LUFS 편차 검사 (규칙 5-1: 씬 -14 / BGM 언더베드 -26).
- 용어집/금지어 검사 (바이블 glossary·banned_phrases, 규칙 5-5 포함).
- 사실 시트 검사 (규칙 5-3): Scene.fact_refs() ⊆ Manifest.fact_sheet.facts,
  파생 에셋 fact_sheet_hash 불일치 시 AssetModel.needs_rerender 플래그.
"""
