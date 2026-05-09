# Activity / Health API

Activity는 활동 로그 조회, Health는 서버 상태 확인을 제공합니다.

## Endpoint

| Method | Path | Auth | 설명 |
| --- | --- | --- | --- |
| GET | `/api/v1/activity/logs?limit=50` | 권한 필요 | 최근 활동 로그 |
| GET | `/api/v1/health/` | 공개 | 서버 상태 확인 |

## Activity 권한

다음 권한 중 하나가 필요합니다.

- `activity.view_activitylog`
- `api.view_activitylog`

## Activity query

| Query | 설명 |
| --- | --- |
| `limit` | 반환 개수, 기본 50, 1~200 |

## Health 응답

```json
{
  "status": "ok",
  "application": "template2-api"
}
```

## 오류

| Status | 상황 |
| --- | --- |
| 401 | Activity 조회 시 로그인 필요 |
| 403 | Activity 조회 권한 없음 |

## 관련 모듈 문서

- `docs/modules/activity-health.md`
