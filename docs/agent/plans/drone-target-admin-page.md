# ExecPlan: Drone Target Admin Page

## 목표
- superuser만 `drone_sop_target` row를 조회, 추가, 수정, 삭제할 수 있는 관리 페이지를 제공한다.
- 기존 line-dashboard/Drone API 구조 안에서 UI와 API를 연결한다.

## 현재 상태
- `DroneSopTarget`은 `target_user_sdwt_prod`, `line_id`를 가진 기존 모델이며 schema 변경은 필요 없다.
- 기존 `/api/v1/line-dashboard/notification-targets`는 operator 중심의 알림 설정 API이고, target 자체 수정/삭제 API는 없다.
- Line dashboard 프론트는 `RequireAuth` 셸과 React Router children 구조를 사용한다.

## 범위
- 수정: `apps/api/api/drone` selector/service/view/url/test, `apps/web/src/features/line-dashboard` API/hook/page/route/export, navigation config.
- 제외: DB schema/migration, 기존 mapping/channel/recipient 편집 UI, 기존 알림 설정 화면 동작 변경.

## 설계
- API: `/api/v1/line-dashboard/admin/drone-targets`에 GET/POST/PATCH/DELETE를 추가한다.
- 권한: 모든 method에서 인증 후 `request.user.is_superuser`만 허용한다.
- 데이터: target 삭제 시 mapping/channel/recipient/needtosend_rule은 cascade되고 dispatch의 target FK는 null 처리된다. UI에는 관련 count를 보여준다.
- 프론트: `/ESOP_Dashboard/admin/drone-targets` route에 table + inline form 기반 업무형 관리 화면을 추가한다.

## 실행 단계
- [x] Backend selector/service/API/test 추가
- [x] Frontend API/query/page/route/navigation 추가
- [x] 변경 파일 import/export 정합성 점검
- [x] focused backend test와 frontend lint/audit 실행

## 검증
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py test api.drone.tests.DroneSopTargetAdminTests --keepdb`
- `npm run web:lint`
- `npm run agent:audit:web-boundary`
- `npm run agent:audit:ui`

## 위험과 대응
- 위험: target 삭제가 mapping/recipient/channel/rule 설정을 함께 삭제하고 기존 dispatch의 target 연결을 비운다.
- 대응: API 응답과 UI에서 관련 count를 노출하고 삭제 확인 문구를 둔다.
- 위험: 기존 operator 알림 설정 API와 책임이 섞일 수 있다.
- 대응: `/admin/drone-targets` 별도 endpoint와 page로 분리한다.

## 진행 기록
- 2026-07-06: superuser 전용 target 관리 화면/API를 별도 admin route로 구현하기로 했다.
- 2026-07-06: backend focused test, web lint, frontend/backend boundary audit, UI audit가 통과했다.
