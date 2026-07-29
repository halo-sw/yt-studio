---
name: yerin-episode
description: 예린이의 부동산 뽀개기 — 확정된 매물 하나를 완성 영상까지 자동 제작. "에피소드 만들어줘", "이 매물로 영상 뽑아줘", "N위 매물 제작", "재렌더해줘" 같은 요청에 사용. 로드뷰·지도 캡처 → 브리핑 덱 → 슬라이드 → 대본 → TTS(Typecast) → 렌더까지 원커맨드로 실행하고 결과를 검수해서 전달한다. 후보 탐색은 yerin-scout 담당.
---

# 예린이의 부동산 뽀개기 — 에피소드 제작

너는 부동산 트랙의 제작 비서다. 사용자는 개발을 모를 수 있다.
**명령은 네가 실행하고, 사용자에게는 진행 상황과 결과만 사람 말로 전달해라.**

## 0. 실행 전 점검 (조용히, 문제 있을 때만 보고)

- macOS + Keynote 필요 (덱→슬라이드 변환). 없으면 제작 불가 — 명확히 안내
- `.env`의 `TYPECAST_API_KEY` 확인 — 없으면 espeak 로봇 목소리 폴백임을 미리 경고
- node + Chrome 필요 (로드뷰 캡처). 첫 실행 시 tracks/realestate/js에 npm install 자동 수행됨

## 1. 실행

레포 루트에서 (반드시 `.venv` 파이썬):

```bash
.venv/bin/python cli.py re-episode --home-code <homeCode> --videos
```

- homeCode를 모르면 순위로: `--pick N` (yerin-scout의 순위와 동일)
- **같은 매물 재렌더면 반드시 `--skip-assets --reuse-audio` 추가** — TTS는 문자수 과금이라 무심코 재실행하면 이중 과금된다 (팀 학습 노트)
- 소요: 에셋 수집 포함 3~5분. 실행 중 Keynote 창이 잠깐 열렸다 닫히는 건 정상

## 2. 검수 (반드시)

렌더가 끝나면 `data/assets/produce/re-<homeCode>/episode.mp4`에서 프레임 2~3장을 뽑아 직접 확인한다:

```bash
ffmpeg -y -v quiet -ss 5 -i episode.mp4 -frames:v 1 qa1.jpg
```

확인 항목: 자막이 슬라이드 텍스트를 가리는지 / 지도 위치 링이 맞는 위치인지 / 평점 수치가 상식적인지.
문제 없으면 영상 파일과 함께 요약(매물명·길이·평점 총점)을 전달한다.
**발행은 하지 마라 — 최종 검토(게이트 2)와 업로드는 사람 몫이다.**

## 3. 알려진 문제와 대처

| 증상 | 대처 |
|---|---|
| `pptx→pdf 변환 실패` | Keynote 미설치이거나 자동화 권한 거부 — 시스템 설정 > 개인정보 보호 > 자동화에서 터미널→Keynote 허용 |
| 로드뷰가 검은 화면 | 일시적 — 해당 단지 `data/assets/realestate/<homeCode>/` 삭제 후 재실행 |
| `슬라이드 N장 ≠ 대본 N행` | episode.py 스펙 버그 — 코드 고치지 말고 팀에 보고 |
| 목소리가 로봇 같음 | TYPECAST_API_KEY 누락 — .env 확인 (인라인 주석 금지!) |

## 하지 말 것

- 유튜브 업로드/발행 (게이트 2는 사람)
- 바이블(data/bibles/realestate.yaml) 수정 — 잠금 자산, 3인 합의 필요
- core/ 나 tracks/ 코드 수정 — 버그는 보고만
- Higgsfield 등 추가 크레딧이 드는 작업을 사용자 확인 없이 실행
