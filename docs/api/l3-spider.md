# L3 Spider API

L3 Spider API는 read-only mount된 `daily_anomaly` Parquet 파일을 조회해 반도체 이상감지 대시보드 데이터를 반환합니다.

## 공통

| 항목 | 값 |
| --- | --- |
| Prefix | `/api/v1/l3_spider/` |
| Auth | Django session 로그인 필요 |
| Data root | `L3_SPIDER_DATA_ROOT` |
| Request/Response | 조회 API는 camelCase. 설정 CRUD 입력은 snake_case, 응답은 camelCase |
| Side effect | 조회 endpoint는 없음. `mail-rules/trigger`만 메일 발송 이력을 쓰고 Mail API를 호출 |

## Data Layout

`L3_SPIDER_DATA_ROOT` 아래 파일은 아래 구조로 조회합니다.

```text
{date}/{lineId}/{processId}/{edsStep}/{filename}
```

파일명은 확장자 없는 `step_seq#ppid#index` 형식을 기본으로 지원합니다.

```text
2025-01-15/L1/P1/EDS_M/S1#PPID_A#0
```

호환을 위해 `S1#PPID_A#0.parquet`도 같은 방식으로 파싱합니다. `data.parquet`처럼 파싱할 수 없는 파일명은 Parquet 내부의 `step_seq`, `ppid` 컬럼을 사용합니다.

## Endpoints

| Method | Path | 설명 |
| --- | --- | --- |
| `GET` | `meta` | 선택 가능한 날짜, Line, Process, EDS Step과 availability를 반환 |
| `POST` | `summary` | 선택 조건 기준 통계, step/PPID, bin, High Risk 목록을 반환 |
| `POST` | `data` | 선택 조건과 차트 필터 기준 Plotly 표시용 row 목록을 반환 |
| `GET` | `mail-rules` | 로그인 사용자 소유 메일 발송 rule 목록을 반환 |
| `POST` | `mail-rules` | 로그인 사용자 소유 메일 발송 rule 생성 |
| `PATCH` | `mail-rules/{id}` | 로그인 사용자 소유 메일 발송 rule 수정 |
| `DELETE` | `mail-rules/{id}` | 로그인 사용자 소유 메일 발송 rule 삭제 |
| `GET` | `mail-rules/{id}/permissions` | owner가 메일 rule 공유 권한 목록 조회 |
| `PUT` | `mail-rules/{id}/permissions` | owner가 메일 rule 공유 권한 전체 교체 |
| `POST` | `mail-rules/trigger` | Airflow token으로 due rule을 처리하고 Mail API 호출 |

## Summary Response 주요 필드

| 필드 | 설명 |
| --- | --- |
| `ppidEqcs` | PPID별 전체 EQPCH 후보 |
| `ppidHighRiskEqcs` | PPID별 High Risk가 발생한 EQPCH 후보. EQPCH 선택 패널은 이 값을 사용 |
| `eqcAnomalyBins` | EQPCH별 Warning 또는 High Risk가 발생한 bin 후보 |
| `eqcHighRiskBins` | EQPCH별 High Risk가 발생한 bin 후보. EQPCH 선택 패널의 숫자 hint는 이 값의 개수를 사용 |

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

메일 rule 생성/수정은 제외 필터와 같은 문자열 패턴을 사용합니다.

```json
{
  "name": "L3 Spider 알림",
  "severity_mode": "high_risk",
  "receiver_emails": ["name@samsung.com"],
  "schedule_type": "daily",
  "send_time": "09:00",
  "timezone": "Asia/Seoul",
  "line_id": "*",
  "process_id": "*",
  "eds_step": "*",
  "step_seq": "*",
  "ppid": "*",
  "eqpch": "EQC_A",
  "bin_name": "*",
  "date_from": null,
  "date_to": null,
  "is_active": true,
  "memo": ""
}
```

`severity_mode`는 `high_risk` 또는 `warning_or_high_risk`를 지원합니다. Airflow trigger는 `Authorization: Bearer <AIRFLOW_TRIGGER_TOKEN>` 헤더가 필요하며, body의 `limit`으로 한 번에 처리할 최대 rule 수를 제한할 수 있습니다.

메일 rule은 owner 외 사용자에게 `read` 또는 `write` 권한을 공유할 수 있습니다.

```json
{
  "permissions": [
    { "user": "name@samsung.com", "access_level": "read" },
    { "user": "engineer.username", "access_level": "write" }
  ]
}
```

`read` 권한자는 rule 전체 설정을 볼 수 있고, `write` 권한자는 rule 조건/수신자/발송 시각/활성 여부를 수정할 수 있습니다. 권한 관리와 삭제는 owner만 가능합니다. 메일 본문에는 `L3_SPIDER_MAIL_TARGET_URL` 또는 `FRONTEND_BASE_URL + /l3_spider` 기준의 L3 Spider 이동 링크가 포함됩니다. 이벤트별 링크에는 `date`, `lineId`, `processId`, `edsStep`, `stepSeq`, `ppid`, `eqpch`, `binName` query param이 붙으며, Web 화면은 해당 값을 읽어 조건을 자동 선택합니다.

## 오류

| Status | 조건 |
| --- | --- |
| 400 | 안전하지 않은 경로 segment 또는 폴더가 아닌 데이터 root |
| 401 | 로그인하지 않은 사용자 또는 Airflow trigger token 불일치 |
| 404 | `L3_SPIDER_DATA_ROOT` 경로 없음 |
