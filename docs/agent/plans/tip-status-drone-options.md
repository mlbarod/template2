# ExecPlan: tip-status drone options

## 목표
- `/tip-status`의 user_sdwt_prod 선택지를 account affiliation이 아니라 ESOP Dashboard와 같은 `drone_sop_target` 기준으로 제공한다.
- 선택지는 `station_master.sdwt_prod_lookup`에 존재하는 `drone_sop_target.target_user_sdwt_prod`만 포함한다.

## 현재 상태
- ESOP Dashboard line selector는 `/api/v1/line-dashboard/line-ids`를 호출하고, `drone_sop_target.line_id` distinct 값을 사용한다.
- `/tip-status`는 `/api/v1/account/line-sdwt-options`를 호출해 account affiliation 기반 line/user_sdwt_prod 옵션을 사용한다.
- `station_master` selector에는 `sdwt_prod_lookup` 값 집합 facade가 있다.

## 범위
- 수정: `api.drone` selector/view/url/test
- 수정: `apps/web/src/features/line-dashboard` API facade
- 수정: `apps/web/src/lib/affiliation` line-dashboard option hook
- 수정: `/tip-status` page import/query source
- 제외: DB schema/migration, account 공용 endpoint 제거, ESOP Dashboard line selector 변경

## 설계
- 새 endpoint: `GET /api/v1/line-dashboard/line-sdwt-options`
- 응답 shape은 기존 `/api/v1/account/line-sdwt-options`와 맞춘다.
- backend는 `DroneSopTarget(line_id, target_user_sdwt_prod)`를 그룹화하고, `station_master_selectors.list_distinct_sdwt_prod_lookup_values()`로 필터링한다.
- frontend `/tip-status`는 feature boundary를 지키기 위해 `@/lib/affiliation`의 line-dashboard option hook을 사용한다.

## 실행 단계
- [x] drone selector 추가
- [x] drone view/url 추가
- [x] frontend API/hook 추가
- [x] `/tip-status` query source 변경
- [x] 테스트와 audit 실행

## 검증
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py test api.drone api.observer`
- `npm run agent:audit:api-boundary`
- `npm run agent:audit:web-boundary`
- `git diff --check`

## 위험과 대응
- 위험: account 공용 옵션 API 변경으로 다른 화면 회귀
- 대응: account endpoint는 유지하고 `/tip-status`만 line-dashboard endpoint로 전환한다.
- 위험: 기존 line-dashboard 설정 옵션과 충돌
- 대응: 새 selector/endpoint를 별도로 추가하고 기존 mapping option selector는 변경하지 않는다.

## 진행 기록
- 2026-06-28: `/tip-status` 옵션을 `drone_sop_target` 기준으로 전환하기로 결정했다.
- 2026-06-28: `/api/v1/line-dashboard/line-sdwt-options`와 frontend line-dashboard option hook 전환을 구현했다.
- 2026-06-28: drone/observer Django 테스트, backend/frontend boundary audit, whitespace check가 통과했다.
