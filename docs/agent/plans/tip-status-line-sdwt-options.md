# ExecPlan: tip-status line sdwt options

## 목표
- `/tip-status`의 line/user_sdwt_prod 선택지를 Observer line dropdown과 동일하게 `account_affiliation.user_sdwt_prod = station_master.sdwt_prod_lookup` 매칭이 있는 항목으로 제한한다.

## 현재 상태
- `/tip-status`는 `/api/v1/account/line-sdwt-options` 응답을 사용한다.
- `account.selectors.list_line_sdwt_pairs()`는 현재 `account_affiliation`만 조회한다.
- Observer dropdown은 `station_master.sdwt_prod_lookup` 매칭이 있는 affiliation만 반환하도록 변경되어 있다.

## 범위
- 수정: `apps/api/api/data_movement/station_master/selectors.py`
- 수정: `apps/api/api/account/selectors.py`
- 수정: 관련 backend 테스트
- 제외: API response shape, DB schema, frontend UI

## 설계
- `station_master` selector에 `sdwt_prod_lookup` 값 집합을 반환하는 읽기 전용 facade를 추가한다.
- account selector는 해당 facade를 통해 매칭 가능한 lookup key를 얻고, `Affiliation.user_sdwt_prod`를 case-insensitive lookup key로 필터링한다.
- API 응답 shape은 기존 `lines[].lineId`, `lines[].userSdwtProds`를 유지한다.
- migration/env/auth 변경은 없다.

## 실행 단계
- [x] `station_master` selector facade 추가
- [x] `account` line-sdwt selector 필터 적용
- [x] account selector 테스트 갱신
- [x] backend 테스트와 boundary audit 실행

## 검증
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py test api.account api.data_movement.station_master`
- `npm run agent:audit:api-boundary`

## 위험과 대응
- 위험: cross-domain model 직접 import로 boundary audit 실패
- 대응: account에서는 `api.data_movement.station_master.selectors`만 import한다.
- 위험: 대소문자 차이로 실제 매칭 누락
- 대응: station_master lookup과 affiliation 값을 모두 대문자/trim 기준으로 비교한다.

## 진행 기록
- 2026-06-28: `/tip-status` line-sdwt option을 station_master 매칭 기준으로 맞추기로 결정했다.
- 2026-06-28: `station_master` selector facade와 account selector 필터를 추가하고 관련 테스트를 갱신했다.
- 2026-06-28: account/station_master/observer 테스트와 backend boundary audit, diff whitespace check가 통과했다.
