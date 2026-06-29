# Observer API

Observer API는 설비 Observer 화면에 필요한 라인, SDWT, 공정, 설비, 로그 데이터를 제공합니다.

## 호출자

- 브라우저 SPA

## 인증

- GET 조회 API는 익명 호출을 차단하지 않습니다.
- 브라우저 SPA는 세션이 있는 경우 Django session cookie를 함께 전송합니다.

## Endpoint

| Method | Path | 설명 |
| --- | --- | --- |
| GET | `/api/v1/observer/lines` | 라인 목록 |
| GET | `/api/v1/observer/sdwts?lineId=...` | 라인별 SDWT |
| GET | `/api/v1/observer/prc-groups?lineId=...&sdwtId=...` | 공정 그룹 |
| GET | `/api/v1/observer/equipments?lineId=...&sdwtId=...&prcGroup=...` | 설비 목록 |
| GET | `/api/v1/observer/equipment-info/<line_id>/<eqp_id>` | 라인 포함 설비 상세 |
| GET | `/api/v1/observer/equipment-info/<eqp_id>` | 설비 상세 |
| GET | `/api/v1/observer/logs?eqpId=...` | 전체 로그 |
| GET | `/api/v1/observer/logs/eqp?eqpId=...` | EQP 로그 |
| GET | `/api/v1/observer/logs/tip?eqpId=...` | TIP 로그 |
| GET | `/api/v1/observer/logs/ctttm?eqpId=...` | CTTTM 로그 |
| GET | `/api/v1/observer/logs/racb?eqpId=...` | RACB 로그 |
| GET | `/api/v1/observer/logs/esop?eqpId=...` | ESOP 로그 |
| GET | `/api/v1/observer/tkin-prevent/prc-groups?userSdwtProd=...` | T/K-IN Prevent PRC 그룹 목록 |
| GET | `/api/v1/observer/tkin-prevent/processes?userSdwtProd=...&prcGroup=...` | T/K-IN Prevent process_id 목록 |
| GET | `/api/v1/observer/tkin-prevent/step-seqs?userSdwtProd=...&prcGroup=...&processId=...` | T/K-IN Prevent step_seq 목록 |
| GET | `/api/v1/observer/tkin-prevent/matrix?userSdwtProd=...&prcGroup=...&processId=...&stepSeq=...` | T/K-IN Prevent matrix |

## Query 규칙

- `lineId`, `sdwtId`, `prcGroup`는 대문자로 정규화됩니다.
- 필수 query가 없으면 400을 반환합니다.
- Observer drill-down의 `lineId`는 `drone_target.line_id`, `sdwtId`는 `drone_target.target_user_sdwt_prod` 기준입니다.
- PRC/설비 조회는 `drone_target.target_user_sdwt_prod = station_master.sdwt_prod_lookup` 매칭으로 station 데이터를 제한합니다.
- 기준정보와 로그는 기본 DB의 data movement/업무 테이블을 조회합니다.
- 로그 조회 API는 공통으로 `from`, `to`, `limit` query를 지원합니다.
- `from`, `to`는 `YYYY-MM-DD` 또는 datetime 문자열을 받습니다.
- `from`을 생략하면 backend 기본 조회 기간인 최근 60일을 사용합니다.
- `limit`은 양의 정수만 허용하며 최대 5000건으로 제한됩니다.
- frontend 기본 로그 조회는 `limit`을 명시하지 않고 backend 기본 기간 정책을 따릅니다.
- T/K-IN Prevent 화면은 ESOP Dashboard line 선택과 `account_affiliation.line/user_sdwt_prod` 매핑으로 `userSdwtProd` 후보를 정합니다.
- T/K-IN Prevent PRC 후보는 `station_master.sdwt_prod_lookup = userSdwtProd`인 row의 `station_master.prc_group_lookup`에서 가져옵니다.
- T/K-IN Prevent process/step/matrix 조회는 `userSdwtProd`와 `prcGroup`으로 대상 `station_master.ch_main`을 찾습니다.
- T/K-IN Prevent 조회는 `station_master.ch_main`과 `m_tkin_prevent.eqp_id`를 정규화 비교해 대상 설비를 제한합니다.
- tkin Prevent matrix 응답의 `columns[]`는 `lineId`, `eqpId`, `chamberId`, `label`을 포함합니다.

## 예시

```http
GET /api/v1/observer/equipments?lineId=L1&sdwtId=S1&prcGroup=P1
```

```http
GET /api/v1/observer/logs?eqpId=EQP-001
```

```http
GET /api/v1/observer/logs/eqp?eqpId=EQP-001&from=2026-01-01&to=2026-01-31&limit=1000
```

```http
GET /api/v1/observer/tkin-prevent/matrix?userSdwtProd=S1&prcGroup=P1&processId=PROC1&stepSeq=10
```

## 오류

| Status | 상황 |
| --- | --- |
| 400 | 필수 query 누락 |
| 401 | 배포 정책상 인증이 필요한 경우 |
| 404 | 설비 정보 없음 |
| 500 | 기본 DB 조회 실패 |

## 관련 모듈 문서

- `docs/modules/observer.md`
