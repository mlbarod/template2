# Timeline API

Timeline API는 설비 타임라인 화면에 필요한 라인, SDWT, 공정, 설비, 로그 데이터를 제공합니다.

## 호출자

- 브라우저 SPA

## 인증

Django session 기준입니다.

## Endpoint

| Method | Path | 설명 |
| --- | --- | --- |
| GET | `/api/v1/timeline/lines` | 라인 목록 |
| GET | `/api/v1/timeline/sdwts?lineId=...` | 라인별 SDWT |
| GET | `/api/v1/timeline/prc-groups?lineId=...&sdwtId=...` | 공정 그룹 |
| GET | `/api/v1/timeline/equipments?lineId=...&sdwtId=...&prcGroup=...` | 설비 목록 |
| GET | `/api/v1/timeline/equipment-info/<line_id>/<eqp_id>` | 라인 포함 설비 상세 |
| GET | `/api/v1/timeline/equipment-info/<eqp_id>` | 설비 상세 |
| GET | `/api/v1/timeline/logs?eqpId=...` | 전체 로그 |
| GET | `/api/v1/timeline/logs/eqp?eqpId=...` | EQP 로그 |
| GET | `/api/v1/timeline/logs/tip?eqpId=...` | TIP 로그 |
| GET | `/api/v1/timeline/logs/ctttm?eqpId=...` | CTTTM 로그 |
| GET | `/api/v1/timeline/logs/racb?eqpId=...` | RACB 로그 |
| GET | `/api/v1/timeline/logs/jira?eqpId=...` | Jira 로그 |

## Query 규칙

- `lineId`, `sdwtId`, `prcGroup`는 대문자로 정규화됩니다.
- 필수 query가 없으면 400을 반환합니다.
- timeline 전용 DB를 조회합니다.
- 일부 Jira/Drone 관련 로그는 기본 DB를 함께 사용할 수 있습니다.

## 예시

```http
GET /api/v1/timeline/equipments?lineId=L1&sdwtId=S1&prcGroup=P1
```

```http
GET /api/v1/timeline/logs?eqpId=EQP-001
```

## 오류

| Status | 상황 |
| --- | --- |
| 400 | 필수 query 누락 |
| 401 | 인증 필요 |
| 404 | 설비 정보 없음 |
| 500 | timeline DB 조회 실패 |

## 관련 모듈 문서

- `docs/modules/timeline.md`
