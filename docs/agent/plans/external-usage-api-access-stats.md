# ExecPlan: 외부 사용량 API 접속현황 연동

## 목표
- 앱별 접속 현황에서 외부 사용량 API의 `date/appName/accessCount` 데이터를 기존 통계와 함께 표시한다.
- 외부 API URL은 `EXTERNAL_APP_USAGE_API_URLS` 환경변수로 sourceName과 함께 관리하고 코드에 직접 URL을 하드코딩하지 않는다.

## 현재 상태
- `api.activity`는 내부 `ActivityLog(APP_ACCESS)`와 수동 입력 `ExternalAppAccessDailyStat`을 합산해 `/api/v1/activity/app-access-stats`로 반환한다.
- 프론트 `AccessStatsPage.jsx`는 같은 API의 `summary/apps/series`를 그대로 표시한다.
- 외부 API 응답에는 사용자 수가 없으므로 `uniqueUserCount`는 외부 API row에서 `0`으로 처리해야 한다.

## 범위
- 수정할 영역:
  - `apps/api/api/activity/services/activity_logs.py`
  - `apps/api/api/activity/tests.py`
  - `apps/api/config/settings.py`
  - `env/api.common.env`
  - `docs/configuration.md`
  - `apps/web/src/features/access-stats/pages/AccessStatsPage.jsx`
- 수정하지 않을 영역:
  - DB schema/migration
  - 외부 API 인증 구현
  - 외부 데이터 저장/캐싱

## 설계
- 백엔드가 조회 시점에 `EXTERNAL_APP_USAGE_API_URLS`의 source 목록을 순차 호출한다.
- 응답 row는 `date`, `appName`, `accessCount`가 모두 유효한 경우만 사용한다.
- 날짜 범위와 `appId` 필터를 기존 통계 API 요청 기준으로 백엔드에서 적용한다.
- 외부 API row는 `sourceType="external_api"`, 설정의 `sourceName`으로 기존 합산 구조에 넣는다.
- source 호출/응답 실패가 하나라도 있으면 외부 API 통계 전체를 제외하고, 잘못된 row는 source 실패로 보지 않고 skip한다.
- 외부 API 제외 사유는 기존 내부/수동 통계 응답을 유지한 채 `externalUsage.sources[].error`와 `externalUsage.error`에 요약한다.
- 인증은 현재 없고, 향후 토큰 추가가 가능하도록 URL/timeout 설정만 env로 둔다.

## 실행 단계
- [x] env/settings/docs에 외부 사용량 API 설정 추가
- [x] activity service에 외부 API fetch/정규화/합산 추가
- [x] 프론트에 외부 API 오류 표시 추가
- [x] 테스트 추가/수정
- [x] 검증 명령 실행

## 검증
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py test api.activity --keepdb`
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py makemigrations --check --dry-run`
- `npm run lint --workspace web`
- `npm run agent:audit:api-boundary`
- `npm run agent:audit:web-boundary`
- `npm run agent:audit:ui`
- `npm run web:build`

## 위험과 대응
- 위험: 외부 API 장애가 대시보드 전체 실패로 이어질 수 있다.
- 대응: 외부 API 예외를 잡아 외부 API 통계 전체를 제외하고, 기존 내부/수동 통계는 그대로 반환한다.
- 위험: 외부 API에는 사용자 수가 없어 기존 KPI의 unique user 의미와 다르다.
- 대응: 외부 API row는 `uniqueUserCount=0`으로 유지하고 접속횟수/추이에만 반영한다.
- 위험: 오프사이트 환경에서 사내 URL 접근이 불가능할 수 있다.
- 대응: URL 기본값을 비워 외부 API 연동을 끌 수 있고, 실제 URL은 배포 환경별 env에서 주입한다.

## 진행 기록
- 2026-07-02: 사용자 답변에 따라 백엔드 호출, 무인증, 저장 없는 조회 시점 fetch 설계를 확정했다.
- 2026-07-02: 외부 API row 합산, 실패 상태 응답, 프론트 경고 표시, env/docs/tests를 추가하고 검증을 완료했다.
- 2026-07-02: 외부 API와 수동입력 컬럼명을 `date/appName/accessCount` 계열로 통일하고, 수동입력도 `appName.strip().upper()` 값을 저장 키와 표시명으로 사용하도록 변경했다.
- 2026-07-02: 외부 API 설정을 명시적 `sourceName/url` 목록(`EXTERNAL_APP_USAGE_API_URLS`)으로 확장하고, 공통 env의 실제 사내 URL 기본값을 제거했다.
