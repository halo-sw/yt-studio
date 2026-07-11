# CLAUDE.md — channel-factory 개발 브리프

> 이 문서는 레포 루트에 두는 Claude Code용 프로젝트 컨텍스트다.
> 모든 설계 결정은 이미 확정됐다. 개발 중 이 문서와 충돌하는 구현을 하지 않는다.

## 1. 프로젝트 한 줄 요약

3명이 공동 운영하는 유튜브 자동화 스튜디오. 카테고리별 에이전트 5개(일본 머니 / 부동산 / 드라마썰 / 사연 / 플레이리스트)가 소재 발굴 → 대본 → 음성 → 비주얼 → 조립 → 검토 → 예약 발행을 처리하고, 사람은 **소재 확정**과 **최종 검토** 두 게이트에서만 개입한다. 전 트랙 최소 10분 롱폼(플레이리스트는 60분).

## 2. 기술 스택 (확정)

| 레이어 | 선택 | 비고 |
|---|---|---|
| 백엔드 | FastAPI (Python 3.11+) | 파이프라인 코드와 언어 통일 |
| DB | PostgreSQL (Docker) | v0은 SQLite 허용, 스키마는 동일하게 |
| 작업 큐 | Redis + RQ | 렌더·생성 잡. 초기 스케줄링은 APScheduler |
| 프론트 | Next.js + React + Tailwind | `demo/channel_factory_demo.jsx`가 UI 사양 원본 |
| 렌더 | FFmpeg + PIL + pdf2image | 서버 로컬 실행 |
| 외부 API | Anthropic(대본·메타), ElevenLabs(TTS 한/일), YouTube Data API(업로드·경쟁 폴링·지표) | |
| 수동 대기열 | Midjourney, Higgsfield | 공식 API 없음 → 프롬프트 생성까지 자동, 생성·업로드는 사람(비주얼 대기열 화면) |

## 3. 레포 구조 (이대로 생성)

```
channel-factory/
├─ CLAUDE.md
├─ core/
│  ├─ schemas.py        # 씬 JSON v1, 채널 바이블, 에피소드 매니페스트 (Pydantic)
│  ├─ statemachine.py   # draft→scripted→voiced→rendered→reviewed→scheduled→published
│  ├─ scout.py          # 경쟁 채널 폴링(YouTube API), 아웃라이어 감지, 소재 카드 생성
│  ├─ script.py         # Claude API → 씬 JSON (트랙별 시스템 프롬프트 주입, 길이 제어)
│  ├─ tts.py            # ElevenLabs 씬별 mp3 + ffprobe 길이 실측 → duration 기입
│  ├─ visuals/          # 트랙별 비주얼 어댑터 + MJ/Higgsfield 수동 대기열 인터페이스
│  ├─ assemble.py       # FFmpeg 프리셋 3종 + 오디오 2트랙 믹스 + 씬 교체(부분 재생성)
│  ├─ qc.py             # LUFS 편차, 용어집/금지어, 사실시트 버전 해시 검사
│  ├─ publish.py        # 제목 3안·설명·localizations 생성, 예약 업로드 + verify
│  └─ harvest.py        # 24h/7d 지표 수집, 스카우트 가중치 피드백, 클레임 모니터
├─ tracks/
│  ├─ japan/            # persona_jp.py + review_gate.py(감수 2인 로테이션)
│  ├─ realestate/       # parser.py(반자동: 후보 추출→UI 클릭 확정) + bbogaegi.py
│  ├─ drama/            # ssul_writer.py(비평 구조 규칙) + illust_batch.py(인물 카드 주입)
│  ├─ natepan/          # remix_writer.py(모티프 결합 재창작) + omnibus.py
│  └─ playlist/         # library.py(곡 DB) + mix.py + loop_visual.py + curation_note.py
├─ service/
│  ├─ api/              # FastAPI 라우터 (cards, scenes, review, agents, votes, logs)
│  ├─ workers/          # RQ 잡: generate, regen_scene, render, publish, poll_competitors
│  └─ web/              # Next.js — 에이전트 레일 / 생성 플로우 / CapCut식 타임라인
├─ demo/channel_factory_demo.jsx   # UI 사양 원본 (이식 대상)
└─ data/                # 에셋 스토리지, 채널 바이블 yaml
```

## 4. 데이터 모델 (핵심 3종 — schemas.py에 Pydantic으로)

```python
# 씬 JSON v1 — 전 트랙 공용
Scene { scene_id:int, track:str, chapter:str, narration:str, caption:str,
        visual:{ type:"slide|chart|doc_highlight|illust|clip|loop_art",
                 ref:str, effect:"kenburns|zoom_callout|none" },
        duration: float|None,               # tts.py가 실측 후 기입
        context:{ prev_tail:str, next_head:str } }   # 부분 재생성 시 억양·문맥 연결용

# 채널 바이블 — 채널당 1개, 잠금 자산 (data/bibles/{channel}.yaml)
Bible { voice_id, voice_params{stability,similarity,speed}, style_anchors[이미지 경로],
        subtitle_tokens, lut, bgm_set, character_refs, glossary{}, banned_phrases[] }

# 에피소드 매니페스트 — 영상당 1개
Manifest { episode_id, track, outline, chapters[],
           fact_sheet:{ version_hash, facts:{key:value} },   # 수치의 단일 출처
           cast_cards[]{name, appearance} }                   # 드라마썰 인물 외형 잠금
```

상태머신: `draft → scripted → voiced → rendered → reviewed → scheduled → published`
카드 필드: `owner(맡은 사람, 잠금)`, `approved_by(소재 확정자)`, 모든 전환은 audit_log에 기록.

## 5. 절대 규칙 (검증에서 확정된 설계 제약 — 위반 금지)

1. **오디오 2트랙**: 내레이션·효과음=씬 레이어(-14 LUFS), BGM=에피소드 글로벌 트랙(-26 LUFS 언더베드, 최종 믹스에서 합성). 씬 교체 시 BGM은 건드리지 않는다.
2. **부분 재생성**: 씬 단위로만. 재생성 시 바이블 잠금 자산 + prev_tail/next_head 컨텍스트 자동 주입. 경계 50~100ms 크로스페이드.
3. **사실 시트 단일 출처**: 수치는 씬에 직접 쓰지 않고 fact_sheet 참조. 파생 에셋(차트)은 version_hash 바인딩 → 불일치 시 qc.py가 자동 재렌더 플래그.
4. **셀프 검수 금지**: `approved_by == 요청자`면 리뷰 승인 API가 403. 클레임 잠금: owner가 있는 카드는 타인이 상태 전환 불가.
5. **저작권 규칙**: 드라마썰 대본은 줄거리 서술 총량 상한+씬당 해석 의무(비평 중심), 재연 컷 프롬프트에 배우명·작품 스틸 참조 금지. 네이트판은 복수 사연 모티프 결합 재창작. 라이선스 메타 없는 클립은 ingest 거부(격리 계정 포함).
6. **YouTube 발행**: API 감사(audit) 통과 전까지 "예약 초안 업로드 → 사람이 공개 전환" 하이브리드. publish 후 상태 verify 필수.
7. **길이 제어**: 10분 = 씬 26~32개 = 3,300~3,600자(일어 3,500자). TTS 실측 합산 후 미달 시 지정 챕터 보강 씬 요청. 훅은 40초 내, 미드롤 지점(4/7/10분) 직전 클리프행어.
8. **관제 임계**: ElevenLabs 사용량 80% 경고, 재생성 크레딧 별도 집계. 실패 잡 자동 재시도 2회 후 알림.

## 6. UI 사양 (demo/channel_factory_demo.jsx 이식)

- **에이전트 레일**(좌측): 에이전트 5개 + 실시간 상태 뱃지
- **생성 플로우**(Runway식): 소재 카드 → 설정 칩 → 생성 시작 → 4단계 진행률
- **편집 화면**(CapCut식): 프리뷰 캔버스 + 멀티트랙 타임라인(장면/자막/목소리/BGM 글로벌 트랙) + 선택 장면 패널("이 장면만 다시 만들기", "이음새 듣기")
- **용어는 데모의 일상어 그대로** 사용: 내가 맡기, 소재 확정, 이 장면만 다시 만들기, 발행 예약. 개발 용어(claim, regen)는 코드 내부에서만.
- 추가 화면: 홈 할 일 피드(받은편지함 패턴), 함께 결정(2/3 투표), 기록(감사 로그+사용량)

## 7. 마일스톤 (병렬 5트랙 전제, M1이 최우선)

- **M0 (2~3일)**: 레포 초기화, schemas.py, statemachine.py, DB 모델, 채널 바이블 yaml 5개 초안
- **M1 (1주)**: CLI로 파이프라인 e2e — script→tts→assemble(playlist_1h + longform_16x9 프리셋, 2트랙 믹스) → **플레이리스트 60분 1편 + 일본 12분 1편 실제 산출** (비주얼은 플레이스홀더 허용)
- **M2 (1~2주)**: service 레이어 — FastAPI + 웹(데모 이식), 부분 재생성 잡, 셀프검수/잠금/감사로그, 비주얼 수동 대기열
- **M3 (1주)**: scout 경쟁 폴링+아웃라이어, japan 감수 게이트, natepan 각색기, publish 하이브리드
- **M4**: realestate 파서 반자동 UI, drama 인물 카드, harvest 지표 피드백, qc 고도화

## 8. 환경 변수 (.env.example로 생성)

```
ANTHROPIC_API_KEY=        # 대본·메타 생성
ELEVENLABS_API_KEY=       # TTS (한/일)
YOUTUBE_API_KEY=          # 경쟁 폴링(읽기)
YOUTUBE_OAUTH_CLIENT_ID=  # 채널별 업로드 (channel별 token은 data/tokens/)
YOUTUBE_OAUTH_SECRET=
DATABASE_URL=
REDIS_URL=
TELEGRAM_BOT_TOKEN=       # 관제 알림 (선택)
```

## 9. Claude Code 첫 세션 프롬프트 (순서대로)

1. "CLAUDE.md를 읽고 M0을 수행해줘: 레포 구조 생성, core/schemas.py에 씬 JSON v1·바이블·매니페스트 Pydantic 모델, statemachine.py, SQLAlchemy 모델, 채널 바이블 yaml 5개 초안까지. 각 모델에 5장의 절대 규칙이 어떻게 반영됐는지 주석으로 남겨줘."
2. "M1: script.py(길이 제어 포함)와 tts.py를 구현하고, assemble.py에 playlist_1h 프리셋(loudnorm→크로스페이드→루프 비주얼→타임스탬프 생성)을 구현해줘. ElevenLabs 키가 없을 땐 espeak-ng 폴백으로 동작하게. 완료되면 샘플 곡 3개로 3분짜리 미니 플레이리스트를 실제 렌더해 검증해줘."
3. "assemble.py에 longform_16x9 프리셋(씬 이미지+Ken Burns+자막 번인+2트랙 오디오 믹스+미드롤 챕터 마커)과 씬 교체 함수(replace_scene: 부분 재생성 결과를 경계 크로스페이드로 이어붙임)를 구현하고, 씬 3개짜리 샘플로 교체 전후 렌더를 비교 검증해줘."

## 10. 하지 말 것

- MJ/Higgsfield 자동 호출 시도 (비공식 API·계정 정지 리스크) — 수동 대기열로만
- 씬 JSON에 수치 하드코딩, BGM을 씬 오디오에 굽기, 전체 재렌더로 부분 수정 대체
- localStorage 사용(웹), 라이선스 미확인 소재 ingest, 셀프 승인 우회 로직
- 스코프 확장: 대시보드 5화면+에이전트 워크스페이스 외 신규 화면은 3인 합의 전 금지
