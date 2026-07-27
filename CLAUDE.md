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
| 외부 API | Anthropic(대본·메타), Typecast/ElevenLabs(TTS 한/일), YouTube Data API(업로드·경쟁 폴링·지표), Higgsfield CLI(씬 이미지·영상 — 공식 스킬 경유, 옵션) | |
| 수동 대기열 | Midjourney | 공식 API 없음 → 프롬프트 생성까지 자동, 생성·업로드는 사람(비주얼 대기열 화면). Higgsfield는 공식 CLI 공개로 자동 경로 허용(아래 10장) |

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
9. **비용 사전 고지**: 이미지·영상을 생성하기 전에 **예상 차감 크레딧을 먼저 출력**한다. `core/visuals/credits.py`가 `_run_hf` 단일 관문에 걸려 있어 자동으로 나가며, 배치는 `credits.Batch(...)`로 감싸 앞뒤 잔액 차이로 실측을 대조한다. 단가표에 없는 모델은 `?cr`로 뜨는데, 이건 "얼마 나갈지 모르는 채로 태우는 중"이라는 경고이므로 **먼저 단가를 확인해 표에 추가**한다. 모든 작업(실패 포함)은 `data/usage/higgsfield.jsonl` 원장에 남는다 — 실패가 크레딧을 안 태웠다는 보장이 없다.

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

- MJ 자동 호출 시도 (비공식 API·계정 정지 리스크) — 수동 대기열로만. Higgsfield는 공식 CLI/스킬(.agents/skills/higgsfield-*)이 공개되어 **옵션으로 자동 호출 허용** (2026-07 갱신) — 단, 반드시 공식 CLI 경유, 크레딧 사용량은 관제(5-8)에 집계
- 씬 JSON에 수치 하드코딩, BGM을 씬 오디오에 굽기, 전체 재렌더로 부분 수정 대체
- localStorage 사용(웹), 라이선스 미확인 소재 ingest, 셀프 승인 우회 로직
- 스코프 확장: 대시보드 5화면+에이전트 워크스페이스 외 신규 화면은 3인 합의 전 금지

## 11. 운영 학습 노트 (실수 재발 방지 — 2026-07 세션에서 확정)

> 아래는 실제 제작 세션에서 겪은 실수와 확정된 해법이다. 에이전트는 같은 실수를 반복하지 않는다.

### 환경·레포
- **세션 시작 시 원격 브랜치부터 확인**: `git branch -a`로 후속 작업 브랜치(예: cli.py·배치 큐가 있는 브랜치)가 있는지 본다. "파일이 없다"고 새로 만들기 전에 반드시 원격을 확인 — 다른 브랜치에 이미 구현돼 있던 사례 있음.
- **채널 서랍 = `channels/` (2026-07-27 구조화)**: 실채널별 폴더(심리학가나디·톡톡드라마썰)에 `말투.md`(채널 커스텀 톤 — 대본·업로드 텍스트가 따름) + `롱폼/`·`숏폼/`(완성본) + `브랜딩/`(채널 자산). 중앙 소재 메모리는 `channels/소재함/`(사람 말로 쓴 소재 카드, 채널별 백로그). `cli.py release`가 트랙→채널 매핑(`data/channels.yaml`의 `dir`)을 보고 완성본을 채널 서랍으로 수집하며, 채널 없는 트랙만 `data/releases/`에 대기. 채널 현황 배치 = `tools/channel_pulse.py`(crontab 매일 09:17 → `data/usage/channel_pulse.jsonl`).
- **Python은 `.venv`(3.12) 사용**: 시스템 python3은 Xcode 3.9라 스펙(3.11+) 미달. `pip` 명령은 PATH에 없음 → `.venv/bin/python -m pip`.
- **.env에 인라인 주석 금지**: cli.py의 경량 로더는 `=` 뒤 전체를 값으로 읽는다. 주석은 반드시 별도 줄에. 빈 키에 주석이 붙으면 쓰레기 값이 truthy가 되어 폴백 로직이 망가진다.

### 렌더 (ffmpeg)
- **drawtext 사용 금지**: Homebrew ffmpeg 병은 freetype 없이 빌드되어 drawtext 필터가 아예 없다. 자막은 assemble.py의 PIL 오버레이 경로(`_caption_overlay_png` + overlay enable)로만. 새 필터를 쓸 땐 바이너리 존재가 아니라 **필터 존재**(`ffmpeg -filters`)를 확인.
- **자막은 타임드 자막이 기본**: caption에는 내레이션 전문을 넣고, 렌더가 문장 단위로 쪼개 글자수 비례 타이밍으로 교체 표시한다(`_caption_windows`). 캡션을 `[:38]`식으로 자르지 않는다 — 문장이 중간에서 잘리는 사고의 원인.
- **모션 클립은 1회 재생 + 마지막 프레임 홀드**(tpad clone). `-stream_loop` 무한 루프는 반복이 티가 나서 금지.
- **자막 폰트**: `data/assets/fonts/Pretendard-Bold.otf` (.env `CF_FONT_PATH`). 시스템 폰트 탐색보다 우선.
- **SAR 혼재 금지**: 실사 스톡 세그먼트는 SAR `1:1`, PIL 카드 세그먼트는 SAR 미설정이라 그대로 concat하면 "Invalid argument"로 죽고 **0바이트 파일**이 나온다. concat 전 모든 비디오 체인에 `setsar=1`을 건다 (`assemble.preset_shorts` 반영 완료).
- **긴 영상 자르고 붙일 땐 filter concat 금지**: `[0:v]split=2`로 앞/뒤를 나누면 concat이 앞부분을 소비하는 동안 뒤쪽 분기가 **영상 전체를 메모리에 버퍼링**한다. 20MB(카드만)는 버티지만 50MB(실사 혼합)면 잘리거나 0% CPU로 교착한다. 같은 파일을 `-ss`/`-t`로 두 번 입력해도 마찬가지. → **키프레임에서 `-c copy`로 잘라 concat demuxer**로 붙인다(`brand.insert_bumper`). 씬 경계는 항상 키프레임이라 오차 0.05초 안. 10분 재인코딩 → 1초.
- **길이 검증 필수**: 위 사고는 ffmpeg가 에러 없이 종료하고 파일도 정상적으로 생겨서 조용히 지나간다. 이어붙이기 함수는 결과 길이를 재서 기대값과 다르면 예외를 던질 것.
- **`cmd | tail && next` 금지**: 파이프라인 종료코드는 마지막 명령(`tail`) 것이라 앞 명령이 죽어도 `&&` 뒤가 실행된다. 낡은 산출물에 후속 처리가 붙는 사고의 원인.
- **zsh는 따옴표 없는 변수도 단어 분리를 안 한다**: `IDS="a b c"; for x in $IDS` → 전체가 한 덩어리. 리터럴 목록이나 배열을 쓸 것.

### TTS (Typecast)
- **감정 프리셋을 반드시 전송**: 씬 콘테의 emotion.tone → `prompt.emotion_preset` 매핑(tts.py `_TONE_PRESETS`). 안 보내면 전부 밋밋한 기본 톤 — "감정이 없다"는 피드백의 원인이었다. 보이스마다 지원 감정이 달라 `_voice_emotions`로 필터링한다.
- **낭독 속도는 보이스별 실측**: Junho(speed 1.0) ≈ 9.5자/초 → 5분 ≈ 2,850자, 10분 ≈ 5,700자. Alena ≈ 7.2자/초. 대본 분량은 실측 비율로 역산할 것 (스펙 7장의 3,300자/10분은 ElevenLabs 기준이라 보이스별 보정 필요).
- **재렌더 시 `--reuse-audio`**: 대본이 같으면 기존 wav 재사용. TTS는 문자수 과금이라 무심코 재실행하면 이중 과금.
- 트랙 보이스 확정: natepan = Junho(`tc_632a7588e7c78a412f5a36cd`). 미확정 트랙은 바이블에 TODO가 남아 있어 첫 보이스(Alena) 자동 선택됨 — 새 트랙 가동 전 voice_id부터 확정.

### 비주얼 (Higgsfield — 하이브리드가 기본)
- **기본 전략은 `core/visuals/higgsfield_gen.py`**: 전 씬 GPT Image 2 1k 실사 프리셋(4cr) + 핵심 씬만 Minimax 모션(6cr/6초). 핵심 씬 = 훅·미드롤 클리프행어·절정·엔딩. 10분 1편 ≈ 80~110크레딧. 전 씬 모션(435cr)은 금지 수준의 낭비.
- **실사 프리셋 고정**: "35mm 필름 스틸, 자연광, 얕은 심도, 일러스트/3D 금지" — 스타일 프리픽스를 빼먹으면 인위적인 일러스트 느낌으로 나온다. 인물·소품 묘사(주인공 외형 등)는 전 씬 프롬프트에 반복해 일관성을 고정.
- **알려진 함정**: ① minimax `--resolution` 플래그는 CLI 타입 버그로 실패 → 생략(서버 기본 768). ② "드라이버로 비틀어 연다"류 묘사는 NSFW 오탐 → 도구·강제 뉘앙스 없는 표현으로. ③ 503/무응답은 일시 장애 → 3분 간격 재시도 루프(생성 함수는 기존 파일 스킵이라 재실행 안전). ④ 이미지 1장 ≈ 2분, 클립 1개 ≈ 1~3분 — 3개 동시 실행이 안전한 상한.
- 단가표(실측): GPT Image 2 2k=7 / 1k=4, NB2=2, NB2 Lite=1, Z Image=0.15 / Kling3.0 Turbo 5s=7.5, Minimax 6s=6, Seedance2.0 5s=22.5.
  **이 표의 단일 출처는 `core/visuals/credits.py`의 `UNIT`이다** — 새 모델을 쓰기 전에 거기부터 추가할 것. 영상은 초당 단가로 환산돼 `--duration`에 비례한다.
- **크레딧은 생성 전에 고지된다**: `_run_hf`가 매 호출마다 `[hf] <모델> — 예상 차감 Ncr`을 찍는다. 배치는 이렇게 감싼다:
  ```python
  from core.visuals import credits
  with credits.Batch("시장 연작 비주얼", track="natepan") as b:
      credits.set_active(b)
      ...  # gen_image / gen_motion
      credits.set_active(None)
  # → [크레딧] '…' 종료 — 예상 412cr · 실제 418cr · 잔액 474cr
  ```
  **예상과 실제가 벌어지면 단가표가 틀렸거나 실패 재시도가 크레딧을 태운 것**이므로 원인을 확인하고 표를 갱신한다.
- **사후 역산은 못 믿는다**: CLI는 작업별 크레딧을 응답에 안 싣고 이력도 최근 20건만 남는다. 파일 개수 × 단가로 역산하면 실패·재시도분이 통째로 빠져 **실제보다 적게 나온다**. 반드시 원장(`data/usage/higgsfield.jsonl`)을 근거로 쓸 것.
