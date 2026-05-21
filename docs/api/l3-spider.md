# L3 Spider API

L3 Spider API는 read-only mount된 `daily_anomaly` Parquet 파일을 조회해 반도체 이상감지 대시보드 데이터를 반환합니다.

## 공통

| 항목 | 값 |
| --- | --- |
| Prefix | `/api/v1/l3_spider/` |
| Auth | Django session 로그인 필요 |
| Data root | `L3_SPIDER_DATA_ROOT` |
| Request/Response | camelCase |
| Side effect | 없음. 파일 read-only 조회만 수행 |

## Endpoints

| Method | Path | 설명 |
| --- | --- | --- |
| `GET` | `meta` | 선택 가능한 날짜, Line, Process, EDS Step과 availability를 반환 |
| `POST` | `summary` | 선택 조건 기준 통계, step/PPID, bin, High Risk 목록을 반환 |
| `POST` | `data` | 선택 조건과 차트 필터 기준 Plotly 표시용 row 목록을 반환 |

## Request Body

`summary`와 `data`는 아래 기본 선택값을 사용합니다.

```json
{
  "dates": ["2025-01-15"],
  "lineIds": ["L1"],
  "processIds": ["P1"],
  "edsSteps": ["EDS_M"]
}
```

`data`는 추가 차트 필터를 받을 수 있습니다.

```json
{
  "selectedEqcs": ["EQC_A"],
  "selectedStepBins": ["S1|||BIN_A"],
  "selectedPpidBins": ["S1|||PPID_A|||BIN_A"],
  "selectedSteps": ["S1"],
  "checkedPpids": ["PPID_A"],
  "checkedBins": ["BIN_A"]
}
```

## 오류

| Status | 조건 |
| --- | --- |
| 400 | 안전하지 않은 경로 segment 또는 폴더가 아닌 데이터 root |
| 401 | 로그인하지 않은 사용자 |
| 404 | `L3_SPIDER_DATA_ROOT` 경로 없음 |
