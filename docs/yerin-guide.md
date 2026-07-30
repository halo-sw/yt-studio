# 예린이의 부동산 뽀개기 — 작동 원리 가이드

> 대상: 파이프라인을 고치거나 확장할 사람. 그냥 쓰기만 할 거면 [yerin-onboarding.md](yerin-onboarding.md)만 보면 됩니다.

## 전체 흐름 (원커맨드 한 번에 일어나는 일)

```
.venv/bin/python cli.py re-episode --pick 1 --videos
        │
        ▼
① 스카우트     tracks/realestate/parser.py
   서울시 청년안심주택 공개 데이터(youth-complexes.json, 88곳)를 읽어
   점수화(역거리·가격·세대수·투어영상 유무) → 후보 정렬.
   수치는 전부 fact_sheet에 적재 (규칙 5-3 — 대본엔 {{fact:key}} 토큰만).
        │
        ▼
② 에셋 수집    tracks/realestate/assets.py  (+ js/capture.js, js/yt_frames.js)
   헤드리스 Chrome(puppeteer)으로 카카오맵 캡처:
   로드뷰 3컷(정면/외관/반대편) + 지도 2컷(근접 마커/광역 위치링).
   공식 홈페이지에 유튜브 투어 영상이 있으면(oEmbed 제목으로 관련성 판정)
   시청 페이지에서 시점별 프레임 4컷 캡처 (임베드는 헤드리스에서 오류 153라 우회).
   산출: data/assets/realestate/<homeCode>/ + assets.json
        │
        ▼
③ 브리핑 덱    tracks/realestate/episode.py → js/deck.js (pptxgenjs)
   에셋+수치+자동 평점(휴리스틱 초안)으로 spec JSON을 만들고
   11~16장 덱(pptx) 생성: 커버→결론→위치→교통→로드뷰→(내부)→개요→가격→평점→총평.
   영상 유무에 따라 슬라이드가 자동으로 늘고 줄어듦.
        │
        ▼
④ 슬라이드 변환  episode.py deck_to_slides() — macOS 전용
   Keynote(AppleScript)로 pptx→pdf → pdftoppm으로 PNG.
   파일명 숫자 = 씬 번호 (produce의 --images 규약).
        │
        ▼
⑤ 대본 생성    episode.py build_spec_and_script()
   슬라이드 순서와 1:1로 맞는 예린 톤 내레이션 템플릿.
   수치는 {{fact:key}} 토큰 → 렌더 직전 facts.json으로 치환.
   슬라이드 수 ≠ 대본 행 수면 assert로 즉시 실패 (씬 밀림 방지).
        │
        ▼
⑥ 렌더        cli.py produce (공용 제작 경로)
   Typecast TTS(바이블 voice_id, 씬별 감정 프리셋) → 타임드 자막 번인
   → FFmpeg 조립 → data/assets/produce/re-<homeCode>/episode.mp4 + meta.txt
```

## 진입점 3개 (전부 같은 엔진)

| 진입점 | 대상 | 위치 |
|---|---|---|
| `/yerin` 스킬 (자연어) | 비개발자 — Claude Code에게 말로 | `.claude/skills/yerin/SKILL.md` |
| 웹 UI 부동산 탭 | 클릭 선호 팀원 | `cli.py ui` → :8787 (잡 러너로 re-episode 실행) |
| CLI 직접 | 개발자·자동화 | `re-scout`, `re-episode --home-code/--pick` |

## 자주 만지게 될 지점

- **대본 문구/구성 바꾸기** → `episode.py`의 `build_spec_and_script()` (슬라이드와 내레이션을 같은 함수에서 쌍으로 관리 — 하나 추가하면 둘 다 추가)
- **덱 디자인 바꾸기** → `js/deck.js`의 렌더러 R.* (색상 상수 INK/AMBER 상단에)
- **평점 기준 바꾸기** → `episode.py`의 `build_ratings()` (휴리스틱 초안 — 발행 전 사람 검토 전제)
- **보이스/자막 스타일** → `data/bibles/realestate.yaml` (잠금 자산 — 3인 합의)
- **관련 트랙 모듈**: `bbogaegi.py`(공고 YAML 하네스, 별도 경로) · `slides.py`(PIL 슬라이드 렌더)와는 병렬 구현 — 통합 논의 필요

## 비용 포인트 (돈 나가는 곳)

- **Typecast TTS**: 문자수 과금 — 같은 대본 재렌더는 반드시 `--reuse-audio`
- **Higgsfield**(캐릭터/모션 재생성 시): 바이블 주석의 외형 잠금 문구 필수, 단가는 CLAUDE.md 11장
- 카카오맵 캡처·유튜브 프레임은 무료 (공개 페이지 스크린샷)

## 알려진 제약

- ④ 단계가 **macOS+Keynote 의존** — 리눅스 서버 이전 시 LibreOffice(soffice) 경로 추가 필요 (`deck_to_slides()` 주석 참조)
- 카카오맵 UI가 바뀌면 `js/capture.js`의 오버레이 셀렉터·사이드바 폭(390px) 보정 필요
- 자동 평점·대본은 **초안** — 게이트 1(소재 확정)·게이트 2(최종 검토)는 사람
