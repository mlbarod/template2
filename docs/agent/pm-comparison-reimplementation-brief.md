# PM Comparison Reimplementation Brief

## 목적

이 문서는 PM comparison 페이지를 다른 채팅방이나 새 작업 세션에서 다시 구현할 때 넘겨줄 수 있는 구현 브리프입니다.
현재 제품 내 표시명은 `PM SPIDER`이며, 사용자-facing route는 `/pm_spider`, API prefix는 `/api/v1/pm_spider/`입니다.

핵심 목표는 설비 PM 기준일을 중심으로 `NPW TRACE`, `NPW OES`, `PW TRACE`, `PW OES` 네 가지 카테고리의 score rank와 raw detail plot을 한 화면에서 비교하는 것입니다. 화면에서는 score가 낮을수록 나쁜 항목으로 간주하고, 가장 낮은 score를 rank 1로 표시합니다.

## 사용자 흐름

1. 사용자는 `Line ID`, `EQP ID`, `PM 기준 시점`을 입력합니다.
2. 선택적으로 `FDC bin`, `PPID`, `Recipe ID`, `Trace params`, `dt values`, source name, row limit을 입력합니다.
3. 조회 시 프론트엔드는 `NPW`와 `PW` pattern에 대해 compare API를 병렬 호출합니다.
4. 응답을 네 개 카테고리로 분해합니다.
5. 사용자는 `NPW TRACE`, `NPW OES`, `PW TRACE`, `PW OES` tab 중 하나를 선택합니다.
6. 선택 카테고리에서 ref PM cycle checkbox를 조정할 수 있습니다.
7. 오른쪽 rank list에서 항목을 선택하면 하단 detail chart가 선택 항목 기준으로 갱신됩니다.

## 데이터 루트

백엔드는 파일 기반 Parquet 데이터만 읽습니다. DB model 또는 migration은 추가하지 않습니다.

- 설정값: `PM_COMPARISON_DATA_ROOT`
- 기본 구조:
  - `${PM_COMPARISON_DATA_ROOT}/data`
  - `${PM_COMPARISON_DATA_ROOT}/result`

`data`는 상세 trace/OES plot을 만들기 위한 원본입니다. `result`는 PM cycle별 rank와 trend를 만들기 위한 scoring 결과입니다.

## Partition 계약

`data`는 Hive-style partition을 사용합니다.

```text
data/
  line_id=<line>/
  eqp_id=<eqp>/
  fdc_bin=<bin>/
  dt=<date>/
  pattern=<NPW|PW>/
  ppid=<ppid>/
  recipe_id=<recipe>/
  data_source=<trace|oes>/
  trace_param_name=<sensor or *>/
  *.parquet
```

`result`는 더 작은 partition set을 사용합니다.

```text
result/
  line_id=<line>/
  eqp_id=<eqp>/
  pattern=<NPW|PW>/
  data_type=<trace|oes>/
  *.parquet
```

화면의 `SP` 표현은 구현상 `PW` pattern입니다. 새 구현에서는 혼동을 줄이기 위해 UI label을 `PW`로 통일하거나, 제품 요구에 따라 label만 `SP`로 매핑하면 됩니다.

## API 계약

### GET `/api/v1/pm_spider/meta`

선택 가능한 partition 값을 반환합니다.

주요 응답 필드:

```json
{
  "lineIds": [],
  "eqpIds": [],
  "fdcBins": [],
  "dtValues": [],
  "pmDates": [],
  "patterns": [],
  "ppids": [],
  "recipeIds": [],
  "dataSources": [],
  "traceParamNames": [],
  "warnings": []
}
```

### POST `/api/v1/pm_spider/compare`

요청 payload는 camelCase입니다.

```json
{
  "lineId": "LINE_DEMO",
  "eqpId": "EQP_DEMO_01",
  "pmTimestamp": "2026-06-02",
  "beforeHours": 6,
  "afterHours": 6,
  "fdcBin": "BIN_DEMO",
  "pattern": "NPW",
  "ppid": "PPID_DEMO",
  "recipeId": "RCP_DEMO",
  "traceParamNames": [],
  "dtValues": ["2026-06-02"],
  "traceDataSource": "trace",
  "oesDataSource": "oes",
  "selectedStep": "",
  "selectedWavelength": "",
  "refPmDates": ["2026-05-20"],
  "limit": 500
}
```

필수 필드는 `lineId`, `eqpId`, `pmTimestamp`입니다. 프론트에서는 `pattern=NPW`와 `pattern=PW` 두 요청을 병렬 실행합니다.

주요 응답 구조:

```json
{
  "filters": {},
  "window": {
    "pmTimestamp": "2026-06-02",
    "pmDate": "2026-06-02"
  },
  "trace": {
    "fileCount": 0,
    "scoreFileCount": 0,
    "rowCount": 0,
    "worstSensor": null,
    "summaryRows": [],
    "trendRows": [],
    "scoreTrendRows": [],
    "cycleSummary": [],
    "refCycles": []
  },
  "oes": {
    "fileCount": 0,
    "scoreFileCount": 0,
    "rowCount": 0,
    "worstStep": null,
    "worstWavelength": null,
    "summaryRows": [],
    "stepRows": [],
    "detailRows": [],
    "scoreTrendRows": [],
    "cycleSummary": [],
    "refCycles": []
  },
  "warnings": []
}
```

## Score Data Schema

`result`는 최소한 아래 컬럼을 가져야 합니다.

```text
line_id
eqp_id
날짜
pattern
data_type
item_name
step
wavelength
score
```

rank는 현재 PM 날짜와 같은 `날짜` row만 대상으로 만듭니다. `score` 오름차순으로 정렬합니다.

PM cycle은 `날짜` 컬럼으로 계산합니다.

- current PM date: `cycleIndex = 0`, `phase = "comp"`
- 이전 PM date: 최신순으로 `cycleIndex = -1`, `-2`, `-3`, `phase = "ref"`

`refPmDates`가 없으면 가능한 모든 ref cycle을 포함합니다. `refPmDates`가 있으면 선택된 ref cycle과 comp cycle만 chart/detail에 포함합니다.

## Raw Data Schema

Trace raw는 최소한 아래 컬럼을 기대합니다.

```text
line_id
eqp_id
fdc_bin
pattern
ppid
recipe_id
trace_param_name
날짜
root_lot_id
lot_id
wafer_id
time
step_time
value
```

Trace chart는 선택된 sensor의 `trendRows`를 사용합니다. x축은 PM cycle overlay에 맞춰 `stepTime`을 우선 사용합니다.

OES raw는 long schema와 wide schema를 모두 수용해야 합니다.

Long schema:

```text
날짜
rcp_step
wavelength
value
```

Wide schema:

```text
날짜
rcp_step 또는 step_seq
100.0
100.5
...
```

wide schema는 wavelength로 해석 가능한 numeric column을 `wavelength/value` long form으로 melt합니다.

## Frontend Feature Structure

기존 프로젝트 규칙상 feature 외부에서는 facade만 import합니다.

```text
apps/web/src/features/pm-spider/
  index.js
  routes.jsx
  api/
    index.js
    pmSpiderApi.js
    queryKeys.js
  hooks/
    usePmSpiderQueries.js
  pages/
    PmSpiderPage.jsx
  components/
    PmSpiderFilterBar.jsx
    PmSpiderCategoryDashboard.jsx
    PmScoreScatterChart.jsx
    TraceSignalPanel.jsx
    CanvasHeatmap.jsx
    CanvasLineChart.jsx
    TraceTrendChart.jsx
    OesSpectrumChart.jsx
    OesHeatmap.jsx
    TraceDeltaTable.jsx
    OesDeltaTable.jsx
    PmKpiCards.jsx
  utils/
    format.js
```

라우팅:

- `routes.jsx`는 `path: "pm_spider"` route를 export합니다.
- `index.js`는 `pmSpiderRoutes`만 명시 export합니다.
- 전역 router는 `@/features/pm-spider` facade만 import합니다.

## Page Layout

업무형 dashboard이므로 landing page처럼 만들지 않습니다. 첫 화면에서 바로 필터와 분석 영역이 보여야 합니다.

권장 layout:

```text
Page shell
  Header
    title: PM SPIDER
    badge: NPW / PW category
    action: 전체 새로고침
  Filter bar
    required row: Line ID, EQP ID, PM 기준 시점, before/after hours, trend limit, 조회
    optional row: FDC bin, PPID, Recipe ID, Trace params, dt values, source names
  Error banner
  Main dashboard
    Ref PM cycle selector
    Warning banner
    Top analysis grid
      Left: PM cycle score scatter chart
      Right: category tabs + summary + rank list
    Bottom detail chart
      Trace: selected sensor step_time overlay
      OES: selected step/wavelength ref/comp spectrum
```

height/scroll 규칙:

- route page root는 `h-full min-h-0 overflow-hidden`을 사용합니다.
- page 내부에서 `h-screen`을 다시 쓰지 않습니다.
- main dashboard scroll owner는 하나만 둡니다.
- rank list처럼 내부 scroll이 필요한 region에는 `min-h-0 overflow-y-auto`를 둡니다.
- chart/detail 영역은 고정 최소 높이를 둬서 데이터 로딩 중 layout shift를 줄입니다.

## Category Model

프론트에서는 compare API 응답을 아래 네 카테고리로 분해합니다.

```js
[
  { id: "npw-trace", label: "NPW TRACE", pattern: "NPW", kind: "trace" },
  { id: "npw-oes", label: "NPW OES", pattern: "NPW", kind: "oes" },
  { id: "pw-trace", label: "PW TRACE", pattern: "PW", kind: "trace" },
  { id: "pw-oes", label: "PW OES", pattern: "PW", kind: "oes" },
]
```

각 category는 다음 값으로 화면을 구성합니다.

- `source`: `kind === "trace"`이면 `data.trace`, 아니면 `data.oes`
- `rows`: `source.summaryRows`
- `rowCount`: `source.rowCount`
- `fileCount`: `source.fileCount`
- `warnings`: `data.warnings`
- `scoreTrendRows`: `source.scoreTrendRows`
- `refCycles`: `source.refCycles`

rank row key:

- trace: `traceSensor || traceParamName || itemName`
- OES: `${step}:${wavelength}`

## Query/State Model

필수 상태:

- `form`: filter input draft
- `payload`: 실제 조회에 사용되는 submitted payload
- `selectedCategoryId`
- `selectedRefPmDates`: `null`이면 서버 기본 ref cycle 전체 사용
- `selectedRankKeys`: category별 선택 rank key map

React Query:

- `usePmSpiderMeta`: meta GET
- `usePmSpiderCategoryResults`: `NPW`, `PW` compare POST 병렬 호출
- `usePmSpiderDetailResult`: 선택 rank 항목 기준 detail 재조회

detail 재조회 payload:

- trace 선택 시 `traceParamNames`를 선택 sensor 하나로 제한합니다.
- OES 선택 시 `selectedStep`, `selectedWavelength`를 넣습니다.
- ref cycle 선택 상태는 `refPmDates`로 같이 보냅니다.

## Backend 구현 포인트

백엔드 파일 구성:

```text
apps/api/api/pm_comparison/
  apps.py
  models.py
  selectors.py
  serializers.py
  services/__init__.py
  tests.py
  urls.py
  views.py
```

역할:

- `selectors.py`: path traversal 방지, partition scan, Parquet read fallback
- `serializers.py`: camelCase 요청 검증, path segment 안전성 검증
- `services/__init__.py`: score rank, cycle 계산, raw trace/OES normalization, JSON-safe 변환
- `views.py`: 인증 적용, serializer 검증, service error를 JSON response로 변환
- `urls.py`: `meta`, `compare` endpoint 연결

보안/안정성:

- 파일 경로에 들어가는 값은 `[A-Za-z0-9_.-]`만 허용하고 `..`을 거부합니다.
- `PM_COMPARISON_MAX_FILES`, `PM_COMPARISON_MAX_META_DIRS` 같은 제한값을 둡니다.
- 없는 컬럼은 가능한 범위에서 fallback하되, chart에 필요한 핵심 컬럼이 없으면 warnings에 설명을 넣고 빈 배열을 반환합니다.

## UI State Requirements

반드시 처리할 상태:

- Meta loading: datalist는 비어 있어도 form은 사용 가능해야 합니다.
- Query loading: 분석 영역에 계산 중 표시를 보여줍니다.
- Empty: 필수 조건 입력 안내 또는 rank 데이터 없음 안내를 보여줍니다.
- Error: API error message를 상단 banner에 표시합니다.
- Fetching: background refresh 중에는 우하단 또는 toolbar에 갱신 중 표시를 둡니다.
- Disabled: 필수 필터가 없거나 조회 중이면 조회 버튼을 비활성화합니다.
- Selected: category tab과 rank row는 색상 외에 border/font weight로도 선택 상태를 표현합니다.

## 구현 순서

1. `api.pm_comparison` Django app을 추가하고 settings/url에 연결합니다.
2. `selectors.py`에서 `data`, `result` partition scan과 Parquet read를 구현합니다.
3. serializer에서 compare 요청을 검증합니다.
4. service에서 meta, compare response shape를 먼저 고정합니다.
5. backend test를 추가합니다.
6. frontend feature folder와 route facade를 만듭니다.
7. API client와 query key, query hook을 만듭니다.
8. page shell과 filter bar를 구현합니다.
9. category tab/rank/dashboard를 구현합니다.
10. trace/OES chart를 연결합니다.
11. ref cycle checkbox와 detail 재조회 흐름을 연결합니다.
12. loading/empty/error/selected 상태를 보완합니다.
13. boundary audit, UI consistency audit, lint/build를 실행합니다.

## 검증 명령

Backend 명령은 Docker Compose `api` 컨테이너에서 실행합니다.

```bash
docker compose -f docker-compose.dev.yml exec -T api python manage.py test api.pm_comparison
docker compose -f docker-compose.dev.yml exec -T api python manage.py check
```

Frontend:

```bash
npm run lint --prefix apps/web
npm run build --prefix apps/web
scripts/agent/check_frontend_boundaries.sh
scripts/agent/check_ui_consistency.sh
```

프로젝트에 audit script 이름이 다르면 `package.json`의 `agent:audit:*` script를 우선 사용합니다.

## 새 채팅방에 붙여넣을 요약 프롬프트

```text
PM comparison 페이지를 새로 구현해줘. 제품 내 표시명은 PM SPIDER이고 사용자-facing route는 /pm_spider이야.

목표:
- PM 기준일 기준으로 NPW TRACE, NPW OES, PW TRACE, PW OES 네 카테고리의 score rank와 raw detail chart를 보여준다.
- score는 낮을수록 나쁜 항목이고 오름차순 rank로 표시한다.
- 사용자는 Line ID, EQP ID, PM 기준 시점을 필수로 입력한다.
- 조회 시 pattern=NPW, pattern=PW compare API를 병렬 호출하고, trace/OES 응답을 네 category tab으로 분해한다.
- 선택 category의 ref PM cycle checkbox, score trend scatter, rank list, 하단 detail chart를 제공한다.
- trace detail은 선택 sensor의 step_time overlay line chart, OES detail은 선택 step/wavelength의 ref/comp spectrum chart다.

API:
- GET /api/v1/pm_spider/meta
- POST /api/v1/pm_spider/compare
- compare 요청은 camelCase이며 lineId, eqpId, pmTimestamp가 필수다.
- compare 응답은 filters, window, trace, oes, warnings를 반환한다.
- trace/oes에는 summaryRows, scoreTrendRows, refCycles, detail/trend rows가 있다.

데이터:
- PM_COMPARISON_DATA_ROOT 아래 data와 result를 사용한다.
- result schema는 line_id, eqp_id, 날짜, pattern, data_type, item_name, step, wavelength, score다.
- 날짜 컬럼으로 current cycle 0과 ref cycle -1, -2를 계산한다.
- data는 Hive-style partition이며 trace는 trace_param_name/value/time/step_time, OES는 long 또는 wide wavelength schema를 처리한다.

구현 규칙:
- frontend는 apps/web/src/features/pm-spider 내부 feature로 만들고 외부 import는 facade만 사용한다.
- JSX 파일은 .jsx, non-JSX는 .js를 사용한다.
- route 내부 h-screen 금지, h-full/min-h-0 기반 dashboard layout을 사용한다.
- shadcn/Radix와 Tailwind semantic token을 우선 사용한다.
- backend는 selector/service/view 분리를 지키고 DB migration은 추가하지 않는다.
```
