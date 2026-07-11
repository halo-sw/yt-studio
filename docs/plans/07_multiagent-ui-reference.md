# 기획서 07 — 멀티에이전트 UI 레퍼런스 리서치와 채택 결정

> 2026-07 리서치. channel-factory는 "카테고리별 에이전트 5개 + 사람 게이트
> 2개"라는 멀티에이전트 시스템이므로, 범용 대시보드가 아니라 **에이전트
> 관제 UI**의 문법을 따른다. 아래는 조사한 레퍼런스와 채택/기각 결정.

## 조사한 레퍼런스 3계열

### A. 함대 관제(Mission Control / Fleet View)

- **AgentsRoom** — 에이전트마다 카드 1장(역할 라벨 + 실시간 상태 + 라이브
  출력 미리보기)을 그리드로 배치. 여러 에이전트가 동시에 일하는 걸 한 화면에서.
- **builderz Mission Control** — 잡 디스패치, 멀티에이전트 워크플로 모니터링,
  **지출(스펜드) 관제**, 감사(govern)를 대시보드 하나로.
- **OpenClaw Mission Control** — 에이전트에게 할당된 태스크를 칸반 보드로 추적.

**채택**: ① 홈 상단을 "지금 에이전트들" 함대 스트립으로 — 에이전트 5개
카드에 현재 단계·진행률·최근 활동 1줄·**사람 대기 여부**를 라이브 표시.
② 워크스페이스에 소재 카드 칸반(상태 컬럼). ③ 지출 관제는 이미 기록›사용량에
있으므로 함대 스트립에서 경고만 배지로 연결.
**기각**: OpenClaw의 CEO→부서장 계층 구조 — 우리는 에이전트 5개가 수평이고
관리자는 사람 3인. 계층 시각화는 과설계.

### B. 휴먼 게이트 = Agent Inbox (Human-in-the-Loop)

- **LangChain agent-inbox** — 에이전트가 interrupt로 멈춘 지점을 Gmail식
  받은편지함으로. 항목마다 **허용 액션이 다르게 구성**(accept/edit/reject 중
  해당되는 것만)되고, "승인이 가장 쉬운 경로"(원클릭)여야 한다는 원칙.
- LangGraph HITL 문서 — 멈춤은 체크포인트 기반이라 **내구적**(며칠 뒤에
  이어서 처리 가능).

**채택**: ① 홈 할 일 피드를 "에이전트가 사람을 기다리는 지점"으로 리프레이밍
— 각 카드에 어느 에이전트가 몇 시간째 기다리는지 표시. ② 유형별 허용 액션
구성: 소재 확정 요청=[확정/넘기기], 최종 검토=[검토하러 가기], 실패=[다시
시도/기록 보기]. ③ 확정은 피드에서 원클릭(상세 진입 강요 금지).
**기각**: 인라인 edit 액션(대본을 피드에서 고치기) — 수정은 편집 화면 D3
장면 패널로만(§5-2 씬 단위 원칙과 충돌 방지).

### C. 에이전트 세션 상세 (Devin식 실행 투명성)

- **Devin 세션 UI** — 계획(plan) 제안이 세션의 최대 체크포인트("나쁜 계획은
  1시간 뒤에 발견되지만, 리뷰된 계획은 1분 만에 잡힌다"). 실행은 단계
  타임라인 + Progress/Shell/Editor 탭 + 전체 리플레이.
- 2026 Agent UX 원칙(fuselab 등) — 인터페이스는 "사용자 의도와 자율 행동
  사이의 **책임(accountability) 레이어**". 다단계 워크플로의 실시간 진행
  공개, 모든 단계에서 개입(pause/redirect) 지점 제공.

**채택**: ① 워크스페이스 D2 "에피소드 실행 상세" — 파이프라인 스테퍼(대본→
목소리→그림→조립→검토→예약) + 단계별 활동 로그 스트림(예: "TTS: 씬 14/28
녹음 · 실측 41.2초"). ② 우리의 '계획 체크포인트' = **소재 확정**(아웃라인
확인 후 확정)과 **대본 완료 시점** — 실행 상세에서 대본(씬 목록)을 훑고
진행시키는 지점을 명시. ③ 리플레이 대신 감사 로그 타임라인(이미 06에 있음)
으로 대체 — 영상 파이프라인은 코드 세션만큼 리플레이 가치가 없음.
**기각**: Shell/Browser식 로우레벨 탭 — 운영자 3인은 비개발 맥락, ffmpeg
로그 원문은 실패 시 기록 화면에서만.

## 설계 반영 요약 (뎁스 맵 00과 함께 적용)

| 반영 위치 | 변경 |
|---|---|
| D0 레일 | 에이전트 카드에 미니 진행률 + `사람 대기` 점멸 배지 |
| D1 홈 | 상단 함대 스트립(관제) + 하단 받은편지함(HITL 인박스) 2단 구성 |
| D1 워크스페이스 | ① 지금 하는 일(스테퍼+로그) ② 소재 칸반 ③ 바이블 드로어 |
| D2 카드 상세 | 아웃라이어 근거·출처·맡기/확정·이력 — '계획 체크포인트' 지점 |
| D2 실행 상세 | 단계 타임라인 + 활동 로그, 조립 완료 시 편집으로 핸드오프 |
| 공통 | 상태 문구는 "에이전트가 ~하는 중 / ~를 기다려요" 화법으로 통일 |

## 출처

- AgentsRoom — https://agentsroom.dev/multi-agent-dashboard
- builderz Mission Control — https://github.com/builderz-labs/mission-control · https://mc.builderz.dev/
- OpenClaw Mission Control — https://www.dplooy.com/blog/openclaw-mission-control-free-ai-agent-dashboard
- LangChain agent-inbox — https://github.com/langchain-ai/agent-inbox
- LangGraph Human-in-the-Loop — https://docs.langchain.com/oss/python/langchain/frontend/human-in-the-loop
- Agent Inbox HIL 해설 — https://prompts.brightcoding.dev/blog/stop-building-bad-ai-agents-agent-inbox-fixes-hil
- Devin 세션 분석 — https://ppaolo.substack.com/p/in-depth-product-analysis-devin-cognition-labs · https://docs.devin.ai/release-notes/overview
- Agent UX 2026 — https://fuselabcreative.com/ui-design-for-ai-agents/
