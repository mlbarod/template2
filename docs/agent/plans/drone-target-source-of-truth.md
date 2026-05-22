# ExecPlan: Drone Target Source Of Truth

## 목표
- Drone runtime의 line/user_sdwt_prod 기준을 `account_affiliation`에서 `drone_sop_target`, `drone_sop_target_mapping`, 실제 `drone_sop` 관측값으로 전환한다.
- 신규 알림 target 생성 시 `account_affiliation`에 없는 임의 line도 허용한다.
- mapping dropdown은 Drone target/mapping/SOP 관측값을 병합해 제공한다.

## 현재 상태
- `apps/api/api/drone/selectors.py` 일부 조회가 `account_affiliation` 또는 `account_selectors`의 소속 목록에 의존한다.
- `apps/api/api/drone/services/table_filters.py` line 필터가 `account_affiliation(line, user_sdwt_prod)` 서브쿼리를 사용한다.
- `apps/api/api/drone/services/channels/user_sdwt_channel.py` 신규 target 생성 전 `line_id_exists()`를 검사한다.

## 범위
- 수정할 영역: Drone selector, table filter, target/channel service, Drone tests.
- 수정하지 않을 영역: DB schema, 기존 migration, account 도메인 모델/selector, frontend API shape.
- `account_affiliation` 기반 seed 기능은 초기 import 도구로 남기되 runtime 조회 기준에서는 제외한다.

## 설계
- `DroneSopTarget.line_id`를 알림 target의 소유 line 기준으로 사용한다.
- line 후보는 `DroneSopTarget.line_id`와 실제 `DroneSOP.line_id` 관측값을 병합한다.
- mapping option은 같은 line의 target 값, 기존 mapping 값, 실제 `DroneSOP.sdwt_prod/user_sdwt_prod` 관측값을 병합한다.
- table line filter는 `drone_sop_target`의 target 목록을 우선 사용하고, fallback으로 `drone_sop.line_id` 직접 필터를 유지한다.
- 신규 target 생성은 normalized line_id가 비어 있지 않으면 account 존재 여부와 무관하게 허용한다.
- migration/env/auth contract 변경은 없다.

## 실행 단계
- [x] Drone selector에서 account runtime 의존을 Drone 기준으로 교체한다.
- [x] table filter SQL을 `drone_sop_target` 기준으로 교체한다.
- [x] target 생성 line 검증에서 account 존재 확인을 제거한다.
- [x] mapping option에 Drone target/mapping/SOP 관측값을 병합한다.
- [x] 관련 tests를 수정/추가하고 Docker Compose api 테스트를 실행한다.

## 검증
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py test api.drone --keepdb`
- 필요 시 특정 테스트부터 실행: `docker compose -f docker-compose.dev.yml exec -T api python manage.py test api.drone.tests.<ClassName> --keepdb`

## 위험과 대응
- 위험: 기존 account 추천 target이 더 이상 목록에 자동 표시되지 않아 빈 목록이 될 수 있다.
- 대응: operator가 임의 line/target을 생성할 수 있게 하고, line 목록은 실제 SOP 관측 line도 병합한다.
- 위험: table filter가 target 미설정 line에서 빈 결과를 반환할 수 있다.
- 대응: `DroneSOP.line_id` fallback 조건을 함께 적용한다.
- 위험: mapping option 후보가 너무 넓어질 수 있다.
- 대응: line_id가 일치하는 SOP 관측값과 해당 line target의 mapping 값을 우선 병합한다.

## 진행 기록
- 2026-05-22: account runtime 의존 제거 방향과 임의 line 허용, 관측값 병합 정책 확정.
- 2026-05-22: selector/table filter/service/tests 변경 완료. `api.drone` 전체 테스트 통과.
