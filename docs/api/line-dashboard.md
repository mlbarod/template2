# Line Dashboard / Drone API

Line Dashboard API는 Drone SOP, 라인 테이블, 히스토리, 알림 설정을 제공합니다.

## 호출자

- 브라우저 SPA
- Airflow 또는 scheduler

## 인증

- 화면 API: Django session
- SOP 수집/파이프라인 trigger: Airflow Bearer token

## Endpoint

| 영역 | Method/Path | 설명 |
| --- | --- | --- |
| 조기 알림 | `GET/POST/PATCH/DELETE /api/v1/line-dashboard/early-inform` | 조기 알림 설정 |
| 테이블 | `GET /api/v1/line-dashboard/tables` | 테이블 조회 |
| 테이블 | `PATCH /api/v1/line-dashboard/tables/update` | 테이블 row 수정 |
| 히스토리 | `GET /api/v1/line-dashboard/history` | 라인 히스토리 집계 |
| 라인 | `GET /api/v1/line-dashboard/line-ids` | 라인 목록 |
| Jira | `GET/POST /api/v1/line-dashboard/jira-keys` | Jira key |
| Jira | `GET /api/v1/line-dashboard/jira-user-sdwt-prods` | Jira 사용자 소속 후보 |
| 알림 대상 | `GET/POST/PATCH/DELETE /api/v1/line-dashboard/notification-targets` | 알림 대상 |
| 알림 매핑 | `GET/POST/PATCH/DELETE /api/v1/line-dashboard/notification-target-mappings` | 대상 매핑 |
| 수신자 | `GET/POST/PATCH/DELETE /api/v1/line-dashboard/notification-recipients` | 수신자 |
| 수신자 권한 | `GET/POST /api/v1/line-dashboard/notification-recipient-permissions` | 수신자 권한 |
| SOP | `POST /api/v1/line-dashboard/sop/<sop_id>/instant-inform` | 단건 즉시 인폼 |
| SOP | `POST /api/v1/line-dashboard/sop/<sop_id>/retry-channel` | 실패 채널 재시도 |
| SOP | `POST /api/v1/line-dashboard/sop/ingest/pop3/trigger` | SOP POP3 수집 |
| SOP | `POST /api/v1/line-dashboard/sop/precheck` | 파이프라인 사전 점검 |
| SOP | `POST /api/v1/line-dashboard/sop/trigger` | SOP 알림 파이프라인 |

## 테이블 조회

```http
GET /api/v1/line-dashboard/tables?table=drone_sop&lineId=L1&recentHours=24
```

주요 query:

- `table`
- `lineId`
- `from`, `to`
- `recentHours`

## 테이블 수정

```json
{
  "table": "drone_sop",
  "id": 123,
  "updates": {
    "comment": "확인 필요",
    "needtosend": 1
  }
}
```

수정 가능한 대표 컬럼:

- `comment`
- `needtosend`
- `instant_inform`
- `status`

## SOP trigger

```http
POST /api/v1/line-dashboard/sop/trigger
Authorization: Bearer <AIRFLOW_TRIGGER_TOKEN>
```

동작:

1. 전송 후보 SOP를 조회합니다.
2. 대상 소속과 채널 설정을 확인합니다.
3. Jira, Messenger, Mail 채널을 실행합니다.
4. 채널별 결과를 저장합니다.

## 오류

| Status | 상황 |
| --- | --- |
| 400 | 잘못된 테이블/파라미터/body |
| 401 | 인증 필요 또는 token 오류 |
| 403 | 권한 없음 |
| 404 | SOP 또는 설정 없음 |
| 500 | DB/파이프라인 처리 실패 |
| 502 | Jira/Mail/Messenger 외부 호출 실패 |

## 관련 모듈 문서

- `docs/modules/line-dashboard.md`
