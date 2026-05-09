# Activity / Health 모듈

Activity는 변경 작업 로그 조회, Health는 서버 상태 확인을 담당합니다.

## Activity 기능

- 최근 ActivityLog 조회
- 조회 권한 검사
- 로그 직렬화

ActivityLog 생성은 `api.common`의 middleware가 수행합니다.

## Activity 권한

다음 중 하나가 필요합니다.

- `activity.view_activitylog`
- `api.view_activitylog`

## Health 기능

Health는 인증 없이 서버 상태를 반환합니다.

```json
{
  "status": "ok",
  "application": "template2-api"
}
```

## 관련 API

- `docs/api/activity-health.md`

## 관련 코드

- `apps/api/api/activity/views.py`
- `apps/api/api/activity/models.py`
- `apps/api/api/activity/selectors.py`
- `apps/api/api/activity/services/activity_logs.py`
- `apps/api/api/health/views.py`
- `apps/api/api/health/services/health_status.py`
- `apps/api/api/common/services/middleware.py`
- `apps/api/api/common/services/activity_logging.py`
