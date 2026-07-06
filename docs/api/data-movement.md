# Data Movement API

파일 기반 DB 적재를 Airflow에서 트리거하는 내부 API입니다.

## 인증

모든 endpoint는 `Authorization: Bearer <AIRFLOW_TRIGGER_TOKEN>` 헤더가 필요합니다.

## 파일 적재 트리거

```http
POST /api/v1/data-movement/<table_name>/load/
```

지원 `table_name`:

| table_name | 처리 대상 |
| --- | --- |
| `m_tkin_prevent` | `/data/data_movement/m_tkin_prevent/incoming/*.csv.deflate` |
| `ctttm_workorder_list` | `/data/data_movement/ctttm_workorder_list/incoming/*CT_*_WORKORDER_*.csv.deflate` |
| `ct_process_comment` | `/data/data_movement/ct_process_comment/incoming/*_CT_PROCESS_COMMENT_*.csv.deflate` |
| `eqp_status_chg` | `/data/data_movement/m_eqp_status_chg/incoming/*m_eqp_status_chg*.csv.deflate` |
| `mi_tip_update_hist` | `/data/data_movement/mi_tip_update_hist/incoming/*mi_tip_update_hist*.csv.deflate` |
| `racb_list` | `/data/data_movement/racb_list/incoming/*racb_list*.csv.deflate` |
| `mes_line_mapping_info` | `/data/data_movement/mes_line_mapping_info/incoming/*_MES_MAPPING_INFO_*.csv.deflate` |
| `station_master` | `/data/data_movement/station_master/incoming/*_STATION_MASTER_*.csv.deflate` |

`ctttm_workorder_list`는 파일명 안의 `CT_MST_WORKORDER` 또는 `CT_MNU_WORKORDER`로 원천 DDL 컬럼 순서를 구분합니다.
두 파일 모두 백틱(`) 구분자를 사용합니다.
`eqp_status_chg`도 백틱(`) 구분자를 사용하며, `eqp_event_key` 기준 upsert와 180일 retention purge를 수행합니다.
`mi_tip_update_hist`도 백틱(`) 구분자를 사용하며, TIP 이력을 timeline 조회용 `eqp_cb` 단위로 변환합니다.
`racb_list`는 comma 구분자를 사용하며, `c_racb_id`별 최신 `update_date` row를 선택한 뒤 `eqp_ids`를 `eqp_cb`로 explode하여 저장합니다.
`mes_line_mapping_info`와 `station_master`도 백틱(`) 구분자를 사용하며, 성공 시 대상 테이블을 전체 교체합니다.

요청 바디는 선택입니다.

```json
{
  "limit": 10,
  "dry_run": false
}
```

응답 예시:

```json
{
  "table_name": "ctttm_workorder_list",
  "processed_count": 1,
  "success_count": 1,
  "failure_count": 0,
  "outcomes": [
    {
      "file_name": "69623_CT_MST_WORKORDER_20260529_1400.csv.deflate",
      "status": "success",
      "row_count": 120,
      "source_type": "MST"
    }
  ]
}
```

실패 파일이 하나라도 있으면 응답은 `500`이며, `outcomes`에 파일별 `error_message`가 포함됩니다.

## ct_process_comment 요약 트리거

```http
POST /api/v1/data-movement/ct_process_comment/summarize/
```

`update_flag='Y'`인 `ct_process_comment` row를 최근 업데이트 순으로 OpenWebUI에 요약 요청합니다.
성공한 row는 `llm_summary`를 저장하고 `update_flag='N'`으로 변경합니다.
실패 row는 `update_flag='Y'`를 유지해 다음 실행에서 재시도합니다.

요청 바디는 선택입니다.

```json
{
  "limit": 100,
  "dry_run": false
}
```

응답에는 `processed_count`, `success_count`, `failure_count`, `skipped_count`, `dry_run_count`, `outcomes`가 포함됩니다.
실패 row가 하나라도 있으면 응답은 `500`입니다.
