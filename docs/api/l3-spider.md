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

`daily_anomaly` 파일명은 항상 확장자 없는 `step_seq#ppid#index` 형식이며, **step_seq가 파일명에 반드시 포함됩니다**(알고리즘 서버가 보장하는 계약). `line_name` 매핑과 `lineNames` 필터가 이 파일명 step_seq에 의존하므로, step_seq 없는 파일명은 `daily_anomaly`에 존재하지 않습니다.

```text
2025-01-15/L1/P1/EDS_M/S1#PPID_A#0
```

`S1#PPID_A#0.parquet`처럼 확장자가 붙어도 동일하게 파싱합니다. 내부적으로 파일명에서 step_seq를 못 읽는 경우 Parquet 내부 `step_seq`/`ppid` 컬럼을 쓰는 방어 코드가 남아 있으나, `lineNames` 필터는 파일명 step_seq에 의존하므로 그런(계약 위반) 파일은 경고 로그와 함께 제외됩니다.

## Endpoints

| Method | Path | 설명 |
| --- | --- | --- |
| `GET` | `meta` | 선택 가능한 날짜, Line, Process, EDS Step과 availability를 반환 |
| `POST` | `structure` | 선택 조건 기준 edsStepSeqs·edsStepPpids를 파일명 스캔만으로 반환 |
| `POST` | `stats` | 선택 조건 기준 통계 요약과 PPID별 last_tkin_time을 반환 |
| `POST` | `summary` | 선택 조건 기준 통계, step/PPID, bin, High Risk 목록을 반환 |
| `POST` | `daily-summary` | 선택 날짜 전체의 line_name×process×eds 요약 매트릭스와 헤드라인을 반환 |
| `POST` | `data` | 선택 조건과 차트 필터 기준 Plotly 표시용 row 목록을 반환 |
| `POST` | `filter-candidates` | 선택 조건 기준 EQPCH/bin 등 차트 필터 후보를 반환 |
| `GET` | `mail-rules` | 로그인 사용자 소유 메일 발송 rule 목록을 반환 |
| `POST` | `mail-rules` | 로그인 사용자 소유 메일 발송 rule 생성 |
| `PATCH` | `mail-rules/{id}` | 로그인 사용자 소유 메일 발송 rule 수정 |
| `DELETE` | `mail-rules/{id}` | 로그인 사용자 소유 메일 발송 rule 삭제 |
| `GET` | `mail-rules/{id}/permissions` | owner가 메일 rule 공유 권한 목록 조회 |
| `PUT` | `mail-rules/{id}/permissions` | owner가 메일 rule 공유 권한 전체 교체 |
| `POST` | `mail-rules/{id}/test-send` | write 권한자가 해당 rule을 단발성으로 테스트 발송 |
| `POST` | `mail-rules/trigger` | Airflow token으로 due rule을 처리하고 Mail API 호출 |

## Summary Response 주요 필드

| 필드 | 설명 |
| --- | --- |
| `ppidEqcs` | PPID별 전체 EQPCH 후보 |
| `ppidHighRiskEqcs` | PPID별 High Risk가 발생한 EQPCH 후보. EQPCH 선택 패널은 이 값을 사용 |
| `eqcAnomalyBins` | EQPCH별 Warning 또는 High Risk가 발생한 bin 후보 |
| `eqcHighRiskBins` | EQPCH별 High Risk가 발생한 bin 후보. EQPCH 선택 패널의 숫자 hint는 이 값의 개수를 사용 |

## Request Body

`structure`, `stats`, `summary`, `data`, `filter-candidates`는 아래 기본 선택값을 사용합니다.

```json
{
  "dates": ["2025-01-15"],
  "lineIds": ["L1"],
  "processIds": ["P1"],
  "edsSteps": ["EDS_M"],
  "lineNames": ["FAB_A"]
}
```

`lineNames`(선택)는 `line_name` 기준 필터입니다. 값이 있으면 서버가 각 파일의 `line_name = resolve(line_id, process_id, step_seq)`(아래 규칙표)를 계산해, 선택된 `line_name`에 속하는 파일만 남깁니다. `lineIds`가 원본 `line_id` 필터라면 `lineNames`는 규칙으로 매핑된 표시용 라인 필터입니다. 경로 검증 대상이 아니며(파일 경로에 직접 쓰이지 않음), 비우거나 생략하면 필터가 적용되지 않습니다.

`daily-summary`는 `dates`(또는 단일 날짜)만으로 그 날짜 전체를 집계하며, 위 필터도 함께 받습니다.

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

`read` 권한자는 rule 전체 설정을 볼 수 있고, `write` 권한자는 rule 조건/수신자/발송 시각/활성 여부를 수정할 수 있습니다. 권한 관리와 삭제는 owner만 가능합니다. 테스트 발송은 write 권한자만 실행할 수 있으며 스케줄 due 여부, `L3SpiderMailDelivery`, `lastSentAt`, `lastCheckedAt`을 갱신하지 않습니다. 메일 본문에는 `L3_SPIDER_MAIL_TARGET_URL` 또는 `FRONTEND_BASE_URL + /l3_spider` 기준의 L3 Spider 이동 링크가 포함됩니다. 이벤트별 링크에는 `date`, `lineId`, `processId`, `edsStep`, `stepSeq`, `ppid`, `eqpch`, `binName` query param이 붙으며, Web 화면은 해당 값을 읽어 조건을 자동 선택합니다.

## line_name 규칙표 (`public.l3_spider_line_name_rule`)

`lineNames` 필터와 Summary 매트릭스는 `(line_id, process_id, step_seq) → line_name` 매핑을 PostgreSQL 규칙표로 해석합니다. 이 매핑값은 코드에 하드코딩하지 않고 Django가 관리하는 `public.l3_spider_line_name_rule`에서 읽습니다.

| 항목 | 값 |
| --- | --- |
| 위치 | `public.l3_spider_line_name_rule` |
| 재로딩 | 프로세스별 최대 5초 TTL 후 활성 규칙 재조회 |
| 활성 규칙 없음 | 모든 값이 `line_id`로 폴백 |
| 정렬 | `priority`, `id` 오름차순 |

주요 컬럼은 `rule_type,line_id,process_id,step_seq,line_name,priority,is_active`입니다.

- `rule_type=override`: `(process_id, step_seq)`로 매칭(line_id 무관), `base`보다 우선
- `rule_type=base`: `(line_id, process_id)`로 매칭(step_seq 무관)
- 빈 칸 또는 `%`/`*` = 와일드카드(대소문자 무시)
- 우선순위: `override` → `base`, 같은 type 안에서는 정확 매칭이 와일드카드보다 우선, 와일드카드끼리는 `priority`, `id` 순서
- 미매칭 시 `line_name = line_id`로 폴백

기존 CSV는 다음 command로 테이블에 적재할 수 있습니다.

```bash
python manage.py import_l3_spider_line_name_rules --dry-run
python manage.py import_l3_spider_line_name_rules --replace
```

## 오류

| Status | 조건 |
| --- | --- |
| 400 | 안전하지 않은 경로 segment 또는 폴더가 아닌 데이터 root |
| 401 | 로그인하지 않은 사용자 또는 Airflow trigger token 불일치 |
| 404 | `L3_SPIDER_DATA_ROOT` 경로 없음 |
