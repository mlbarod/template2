# ExecPlan: 수동 외부 앱 접속현황 입력

## 목표
- 슈퍼유저가 외부 앱의 일별 접속현황을 스프레드시트에서 복사해 붙여넣고, 검증 미리보기 후 기존 앱별 접속현황 대시보드에 합산 표시한다.
- 접속현황 추이를 일별, 주별, 월별 집계 단위로 전환해 확인할 수 있게 한다.

## 현재 상태
- `api.activity`는 내부 앱 화면 진입을 `ActivityLog(action="APP_ACCESS")`로 기록한다.
- `GET /api/v1/activity/app-access-stats`는 `ActivityLog`를 KST 날짜 기준으로 집계한다.
- `apps/web/src/features/access-stats/pages/AccessStatsPage.jsx`는 동일 API를 사용해 KPI, 차트, 순위, 상세 테이블을 표시한다.
- 기존 chart series는 `date` 값을 일자 단위로 받아 표시한다.

## 범위
- 수정할 영역:
  - `apps/api/api/activity` 모델, migration, serializer, selector, service, view, URL, test
- `apps/web/src/features/access-stats` API hook과 대시보드 입력 UI
- `app-access-stats` 조회 API의 `period` 쿼리 파라미터와 chart series 표시
- 수정하지 않을 영역:
  - 외부 서버 API 자동 연동
  - 사용자별 외부 앱 이벤트 원장 저장
  - 일반 사용자 권한 정책
  - 전역 내비게이션 구조

## 설계
- 외부 앱 수동 입력은 일별 집계 테이블 `activity_external_app_access_daily_stat`에 저장한다.
- 저장 키는 `(app_id, stat_date, source_name)`이며 MVP의 `source_name` 기본값은 `manual`이다.
- 붙여넣기 데이터는 backend에서 한 번 더 검증하고, `preview`와 `commit` API를 분리한다.
- `commit`은 유효 행만 `update_or_create`로 반영하며 오류 행이 있으면 저장하지 않는다.
- 기존 통계 API는 내부 `ActivityLog` 집계와 외부 일별 집계를 합산해 같은 응답 구조로 반환한다.
- 기존 통계 API는 `period=day|week|month`를 받아 `series.date`를 각 기간 시작일로 반환한다.
- 주별 집계는 KST 기준 월요일 시작 주, 월별 집계는 해당 월 1일을 기간 시작일로 사용한다.
- 인증/권한은 기존 접속현황 조회와 동일하게 슈퍼유저 전용으로 둔다.
- DB schema, 환경 변수, 파일 mount, 외부 네트워크 계약은 변경하지 않는다.

## 실행 단계
- [x] 외부 수동 통계 모델과 migration 추가
- [x] 붙여넣기 preview/commit serializer-service-view 추가
- [x] 기존 app-access-stats payload에 외부 집계 병합
- [x] backend 테스트 추가
- [x] frontend API mutation과 붙여넣기 미리보기 UI 추가
- [x] 검증 명령 실행
- [x] 일별/주별/월별 보기 단위 API와 UI 추가

## 검증
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py makemigrations --check --dry-run` 통과
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py migrate` 통과
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py test api.activity --keepdb` 통과
- `npm run agent:audit:api-boundary` 통과
- `npm run agent:audit:web-boundary` 통과
- `npm run agent:audit:ui` 통과
- `npm run web:lint` 통과
- `npm run web:build` 통과
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py test api.activity --keepdb` 재통과(일/주/月 테스트 포함)

## 위험과 대응
- 위험: 외부 통계와 내부 이벤트의 unique user 기준이 다르다.
- 대응: 외부 행에는 `sourceType/sourceName`을 응답에 포함해 원천을 구분한다.
- 위험: 붙여넣기 컬럼 오타나 숫자 형식 오류가 운영 중 잘못 반영될 수 있다.
- 대응: preview 단계에서 오류 행을 표시하고 오류가 있으면 commit을 막는다.
- 위험: 같은 앱/날짜를 반복 입력할 때 중복 집계될 수 있다.
- 대응: `(app_id, stat_date, source_name)` 기준 upsert로 덮어쓴다.

## 진행 기록
- 2026-06-29: 수동 스프레드시트 붙여넣기 방식으로 MVP 설계를 확정했다.
- 2026-06-29: 외부 일별 집계 모델, preview/commit API, 기존 통계 병합, 붙여넣기 UI를 구현하고 검증을 완료했다.
- 2026-06-29: dev DB에 `activity.0002_external_app_access_daily_stat` migration을 적용했다.
- 2026-06-29: 일별/주별/월별 보기 단위 확장을 시작했다.
- 2026-06-29: `period=day|week|month` API contract와 화면 보기 단위 컨트롤을 추가하고 검증을 완료했다.
