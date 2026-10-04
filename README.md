# 방송 트렌드 달력

SOOP 방송 준비용 사이트: https://unlucky3d.github.io/trend-calendar/

달력(신작 게임 출시일, 시네티 시작/종료)과 그날의 스트리머 소식, SOOP 트렌드, 게임 트렌드, 신메뉴를 보여 준다.
트렌드는 GitHub Actions(`.github/workflows/update.yml`)가 자동으로 모아 `data/` 에 저장한다.

## 사람이 고치는 파일

GitHub에서 파일을 열고 연필 아이콘으로 수정한 뒤 Commit 하면 1~2분 안에 사이트에 반영된다.

| 파일 | 내용 |
|---|---|
| `data/games.json` | 신작 게임 출시일. `korean` 이 true 면 달력에서 파란색 |
| `data/streamers.json` | 방송을 꺼 둬도 방송국 게시글을 확인할 스트리머. `{"id": "SOOP 아이디", "name": "표시 이름"}` |
| `data/cinety_manual.json` | 시네티 월간 일정표(이미지)를 읽어 옮겨 적은 서비스 기간. 일정표가 바뀌면 사이트에 안내가 뜬다 |

AI에게 맡길 때는 현재 파일 내용을 붙여 넣고 "같은 형식으로 고쳐서 전체를 다시 줘"라고 요청한다.

## 자동으로 만들어지는 파일 (고치지 않는다)

`data/snapshots/YYYY-MM.json`, `data/cinety.json`, `data/food.json`, `data/streamer_peak.json`, `data/steam_names.json`

## 수집 스크립트

| 스크립트 | 하는 일 |
|---|---|
| `scripts/collect.py` | SOOP 인기 카테고리, 인기 방송 |
| `scripts/keywords.py` | 방송 제목 키워드 (시청자 수 기준) |
| `scripts/games_trend.py` | 치지직, 트위치, 스팀 인기 게임 |
| `scripts/streamer_news.py` | 방송국 게시글 중 모집/발표/대회/공지 글. 분류 단어는 파일 위쪽에서 고친다 |
| `scripts/food_news.py` | 프랜차이즈 신메뉴, 편의점 신상 기사 |
| `scripts/cinety.py` | 시네티 공지에서 서비스 기간과 같이보기 일정 |

## 지금 바로 수집하기

Actions 탭 → "트렌드 수집" → Run workflow. 예약 실행은 GitHub 사정으로 자주 늦어지거나 건너뛴다.
