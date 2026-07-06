# Data Movement 모듈

`api.data_movement`는 FTP 등으로 수신한 deflate CSV 파일을 PostgreSQL 테이블로 적재합니다.

## 디렉터리

테이블별 root 아래 `incoming/`에 완료 파일을 둡니다. loader는 파일을 `processing/`으로 atomic move한 뒤 처리하고, 성공/실패 후 처리 파일을 삭제합니다.
Compose 기본 host path는 `./data/data_movement`이고, API 컨테이너에서는 `/data/data_movement`로 mount됩니다.

| 테이블 | 기본 root | 파일 패턴 |
| --- | --- | --- |
| `m_tkin_prevent` | `/data/data_movement/m_tkin_prevent` | `*.csv.deflate` |
| `ctttm_workorder_list` | `/data/data_movement/ctttm_workorder_list` | `*CT_*_WORKORDER_*.csv.deflate` |
| `ct_process_comment` | `/data/data_movement/ct_process_comment` | `*_CT_PROCESS_COMMENT_*.csv.deflate` |
| `eqp_status_chg` | `/data/data_movement/m_eqp_status_chg` | `*m_eqp_status_chg*.csv.deflate` |
| `mi_tip_update_hist` | `/data/data_movement/mi_tip_update_hist` | `*mi_tip_update_hist*.csv.deflate` |
| `racb_list` | `/data/data_movement/racb_list` | `*racb_list*.csv.deflate` |
| `mes_line_mapping_info` | `/data/data_movement/mes_line_mapping_info` | `*_MES_MAPPING_INFO_*.csv.deflate` |
| `station_master` | `/data/data_movement/station_master` | `*_STATION_MASTER_*.csv.deflate` |

`ctttm_workorder_list`는 `CT_MST_WORKORDER`와 `CT_MNU_WORKORDER`의 원천 컬럼 수와 순서가 다릅니다.
loader는 파일명에서 source를 추출한 뒤 MST는 55개 컬럼, MNU는 49개 컬럼 레이아웃으로 백틱(`) 구분 파일을 읽습니다.
`mes_line_mapping_info`는 파일 하나가 테이블 전체 snapshot이므로 새 파일 처리 시 기존 row를 모두 삭제하고 파일 전체를 다시 적재합니다.
`station_master`도 파일 하나를 테이블 전체 snapshot으로 보고 전체 교체 적재합니다.
`eqp_status_chg`는 `eqp_event_key` 기준으로 증분 upsert하고, `eqp_id`가 `E/e`로 시작하지 않거나 `chg_time`이 180일보다 오래된 row를 제외합니다. 저장 시 `eqp_cb=eqp_id-chamber_id`를 생성하며, 적재 후 target의 180일 초과 row도 삭제합니다.
`mi_tip_update_hist`는 TIP 원천 이력을 `tip_event_key` 기준으로 upsert하고, 원천 타입 조합을 timeline event type으로 매핑합니다.
`racb_list`는 `c_racb_id`별 최신 `update_date` row를 고른 뒤 `eqp_ids`를 comma split하여 `eqp_cb` row로 펼쳐 저장합니다.

## 실행 방식

- 수동 실행: Django management command
- 자동 실행: Airflow DAG `data_movement_file_load`
- CTTTM comment 요약 자동 실행: Airflow DAG `ct_process_comment_summary`
- 내부 API: `POST /api/v1/data-movement/<table_name>/load/`
- CTTTM comment 요약 API: `POST /api/v1/data-movement/ct_process_comment/summarize/`
- 파일 수신: Compose `ftp` service

## Airflow 순서

`ct_process_comment`는 `ctttm_workorder_list`의 workorder 목록을 기준으로 적재 대상을 필터링합니다.
따라서 DAG는 `ctttm_workorder_list` 성공 후 `ct_process_comment`를 실행합니다.
`ct_process_comment` 요약은 별도 `ct_process_comment_summary` DAG에서 실행되며, `update_flag='Y'` row를 최근 업데이트 순으로 처리합니다.
`m_tkin_prevent`, `eqp_status_chg`, `mi_tip_update_hist`, `racb_list`, `mes_line_mapping_info`, `station_master`는 독립적으로 실행됩니다.

## 주의사항

전송 중인 파일이 `incoming/*.csv.deflate`로 보이면 안 됩니다. 업로드 프로세스는 임시 파일명으로 전송한 뒤 완료 시 `incoming/`의 최종 파일명으로 rename해야 합니다.

## FTP

Compose의 `ftp` service는 `repo.samsungds.net/docker.io/fauria/vsftpd` 이미지를 사용합니다.
FTP에서 보이는 `data_movement` 디렉터리는 API의 `/data/data_movement`와 같은 host path입니다.

기본 접속 설정은 env로 바꿀 수 있습니다.

```text
FTP_USER=ftpuser
FTP_PASS=ftp1234
FTP_PORT=6380
FTP_PASV_ADDRESS=127.0.0.1
FTP_PASV_MIN_PORT=8076
FTP_PASV_MAX_PORT=8079
DATA_MOVEMENT_HOST_PATH=./data/data_movement
```

운영에서는 `FTP_PASS`와 `FTP_PASV_ADDRESS`를 반드시 배포 환경에 맞게 설정합니다.
