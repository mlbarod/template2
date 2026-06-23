# ExecPlan: PM SPIDER 대시보드

## 목표
- 반도체 설비 PM 기준 시점 전/후의 trace 시계열과 OES 데이터를 실제 Parquet API로 조회하는 대시보드를 추가한다.
- 사용자가 전후 델타 KPI, trace 최악 센서, OES 최악 step/wavelength 후보를 빠르게 확인할 수 있게 한다.
- 사용자가 `LINE_ID`와 설비 ID를 선택한 뒤 `NPW TRACE`, `NPW OES`, `SP TRACE`, `SP OES` 카테고리별 문제 항목 랭킹과 시각화를 카드형 대시보드에서 확인하게 한다.
- score는 낮을수록 나쁜 항목으로 해석하고, 엔지니어가 가장 나쁜 항목을 먼저 보도록 rank를 오름차순으로 표시한다.
- category card 선택 후 전체 rank 목록을 보고, trace rank 항목 선택 시 해당 sensor의 trace data를 line graph로 표시한다.
- data와 result는 `PM_COMPARISON_DATA_ROOT` 바로 아래 같은 depth에 두고, data row의 `날짜` 컬럼으로 PM cycle을 계산한다.

## 현재 상태
- `apps/api/api/l3_spider`가 파일시스템 Parquet 조회 API 패턴을 이미 제공한다.
- `apps/web/src/features/l3-spider`가 React Query 기반 파일 데이터 대시보드 패턴을 이미 제공한다.
- `apps/api/requirements.txt`에는 `pandas`, `pyarrow`, `numpy`가 포함되어 있다.
- `api.pm_comparison`은 단일 요청에서 한 pattern의 trace/OES 결과를 함께 반환한다.
- Pattern partition 값은 `NPW`와 `PW`이며, 화면 카테고리의 `SP`는 `PW` pattern 조회 결과로 표현한다.
- scoring 결과는 `${PM_COMPARISON_DATA_ROOT}/result` Hive-style Parquet에서 읽으며, schema는 `line_id`, `eqp_id`, `날짜`, `pattern`, `data_type`, `item_name`, `step`, `wavelength`, `score`를 사용한다.

## 범위
- 추가: `apps/api/api/pm_comparison`
- 추가: `apps/web/src/features/pm-spider`
- 수정: backend settings/url registry, frontend route registry/navigation
- 수정: PM SPIDER 프론트 대시보드 레이아웃, React Query category 조회 훅, 표시 유틸
- 제외: DB schema/migration, OES 분석 알고리즘 고도화, 데이터 적재/백필, auth 정책 변경
- 수정: `/api/v1/pm_spider/compare` 요청/응답에 선택 ref PM cycle 정보를 추가

## 설계
- 데이터 루트는 `PM_COMPARISON_DATA_ROOT` 설정으로 읽고 기본값은 `/data`로 둔다.
- raw 원본은 `${PM_COMPARISON_DATA_ROOT}/data`, score 결과는 `${PM_COMPARISON_DATA_ROOT}/result`에서 읽는다.
- API prefix는 `/api/v1/pm_spider/`를 사용한다.
- 요청은 line/eqp/fdc bin/pattern/ppid/recipe/PM timestamp/window를 받는다.
- selector는 Hive-style partition 경로를 안전하게 스캔하고 partition 값을 파일 컬럼에 보강한다.
- service는 trace/OES Parquet을 읽어 전/후 window로 나누고 델타 KPI를 계산한다.
- OES는 wide spectrum과 long spectrum 형태를 모두 수용하며, 알고리즘 교체가 쉽도록 service 내부 정규화 함수로 분리한다.
- 프론트엔드는 상단 필터, KPI, trace worst sensor, OES worst step/wavelength, trace trend, OES table을 한 화면에 둔다.
- 새 대시보드는 `NPW`와 `PW` pattern에 대해 compare API를 병렬 호출하고, 응답을 네 개 카테고리 카드로 분해한다.
- `NPW TRACE`와 `SP TRACE`는 trace summary/trend를 사용하고, `NPW OES`와 `SP OES`는 OES wavelength/step summary를 사용한다.
- 각 카드에는 낮은 score 기준 worst rank, row/file count, rank bar를 표시한다.
- 선택된 카테고리의 상세 영역에는 전체 rank 목록을 제공한다.
- trace category에서는 선택된 sensor만 compare API로 재조회해 line graph에 표시한다.
- OES category에서는 선택된 category의 step/wavelength rank table을 표시한다.
- PM 날짜 목록은 `result`의 `날짜` 컬럼에서 수집한다.
- 현재 선택 PM 날짜는 cycle `0` / `comp`, 이전 PM 날짜들은 최신순으로 `-1`, `-2` / `ref`로 내려준다.
- 선택한 OES rank는 해당 step의 raw spectrum을 wavelength x축 line graph로 표시한다.
- compare 요청에 `refPmDates`가 없으면 기존 계산에 포함된 전체 ref cycle을 기본값으로 사용한다.
- compare 요청에 `refPmDates`가 있으면 선택된 ref cycle과 current PM cycle만 score trend/detail raw plot에 포함한다.
- dashboard는 상단 ref cycle checkbox, 좌측 score trend line chart, 우측 NPW/PW 및 Trace/OES tabs와 rank list, 하단 ref/comp detail line graph로 구성한다.

## 실행 단계
- [x] ExecPlan 작성
- [x] Django feature 파일 생성 및 settings/url 연결
- [x] service/selector/serializer/view/test 작성
- [x] React feature 파일 생성 및 route/export 연결
- [x] 홈 내비게이션 연결
- [x] 테스트/audit 실행
- [x] PM SPIDER 명칭 변경 반영
- [x] NPW/PW category 병렬 조회 훅 추가
- [x] 네 개 category card와 선택 상세 대시보드 구현
- [x] 필터바를 LINE_ID/EQP 중심 흐름으로 조정
- [x] frontend lint/audit/build 재검증
- [x] score 오름차순 rank 정렬 반영
- [x] category 상세 전체 rank 선택 UI 구현
- [x] trace rank 항목 선택 기반 line graph 구현
- [x] data/result 디렉터리 분리 반영
- [x] result 기반 PM cycle scatter/rank 구현
- [x] OES wavelength x축 spectrum graph 구현
- [x] ref cycle 선택 요청 필드와 응답 메타 추가
- [x] score trend/tabs/rank/detail 중심 dashboard 재구성
- [x] ref cycle 선택 재계산 UX 구현
- [x] rank 영역이 첫 화면에 보이도록 PM SPIDER workspace 높이와 tab 영역 압축
- [x] trace detail graph x축을 `time`에서 `step_time`으로 변경
- [x] 오른쪽 category 선택을 `NPW TRACE`/`NPW OES`/`PW TRACE`/`PW OES` 단일 tabs 구조로 정리

## 검증
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py test api.pm_comparison`
- `npm run lint --prefix apps/web`
- `npm run agent:audit:web-boundary --prefix apps/web`가 없으면 실행 불가 사유를 보고한다.

## 위험과 대응
- 위험: 실제 데이터 partition 명명이나 dt 포맷이 샘플과 다를 수 있다.
- 대응: `key=value` partition을 동적으로 읽고, 요청 필터는 없는 값이면 wildcard로 처리한다.
- 위험: OES raw schema가 wide/long 사이에서 바뀔 수 있다.
- 대응: wide wavelength 컬럼과 long `wavelength/value` 컬럼을 모두 정규화한다.
- 위험: 대용량 Parquet을 과도하게 읽을 수 있다.
- 대응: path filter, 시간 window filter, 응답 row limit 설정을 둔다.

## 진행 기록
- 2026-06-01: 사용자 답변 기준으로 실제 API 연동 신규 feature 구현 방향을 확정했다.
- 2026-06-01: `api.pm_comparison`과 현재 `pm-spider` React feature의 초기 구현을 추가하고 테스트/audit/build 검증을 완료했다.
- 2026-06-02: 표시명을 `PM SPIDER`로 바꾸고, NPW/PW pattern 기반 네 개 카테고리 카드 대시보드 요구사항을 반영하기로 했다.
- 2026-06-02: 프론트에서 `NPW`/`PW` compare API를 병렬 조회하고, `NPW TRACE`, `NPW OES`, `SP TRACE`, `SP OES` 카드와 선택 상세 영역으로 재구성했다.
- 2026-06-02: score 낮음 우선 rank 정렬과 trace rank 항목 선택 plot 요구사항을 추가 반영한다.
- 2026-06-02: 낮은 score가 나쁜 항목이 되도록 score 산식을 보정하고, rank 항목 선택 시 trace sensor 단일 line graph를 재조회하도록 구현했다.
- 2026-06-02: 사용자 확정 기준에 따라 raw 원본과 score 결과를 분리하고, score 결과의 `날짜` 컬럼으로 PM cycle scatter/rank를 구성하도록 변경했다.
- 2026-06-11: 마운트 규칙에 맞춰 PM Spider 단일 root 아래 `data`와 `result`만 사용하도록 경로 계약을 정리했다.
- 2026-06-02: 카드형 category 나열을 score trend, tab rank, ref cycle selector, 하단 detail graph 중심의 분석 화면으로 재구성한다.
- 2026-06-02: `refPmDates` 요청 필드를 추가해 선택된 ref cycle만 score trend/detail plot에 반영하고, dashboard를 좌측 score trend + 우측 tabs/rank + 하단 ref/comp graph로 재구성했다.
- 2026-06-02: rank card가 좁은 desktop 폭에서도 오른쪽에 보이도록 breakpoint와 높이를 조정하고, trace detail x축을 PM 주기 overlay용 `step_time`으로 바꿨다.
- 2026-06-02: category 선택을 두 단계 탭에서 네 개 category 단일 탭으로 바꾸고, 선택 card 안에 summary와 rank가 함께 보이도록 조정했다.
