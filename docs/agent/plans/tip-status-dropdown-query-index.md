# ExecPlan: tip-status dropdown query index

## 목표
- `/ESOP_Dashboard/tip-status`의 `process_id`, `step_seq` dropdown 조회 지연을 줄인다.
- 이미 정규화된 `m_tkin_prevent` 값을 조회 시점에 다시 `upper(trim())` 처리하지 않는다.

## 현재 상태
- `observer` selector는 `m_tkin_prevent`와 `station_master` 대상 EQP CTE를 조인해 dropdown option을 계산한다.
- `m_tkin_prevent`에는 `line_id` 인덱스만 있어 `eqp_id`, `process_id`, `step_seq`, `registration_level` 기반 조회에 도움이 작다.
- 사용자가 `eqp_id`, `process_id`, `step_seq`, `registration_level`은 이미 대문자 정규화되어 있다고 확인했다.

## 범위
- 수정: `apps/api/api/observer/selectors.py`
- 수정: `apps/api/api/data_movement/m_tkin_prevent/models.py`
- 추가: `apps/api/api/data_movement/m_tkin_prevent/migrations/0002_tkin_prevent_dropdown_indexes.py`
- 수정: `apps/api/api/observer/tests.py`
- 제외: API response shape 변경, frontend 변경, lookup 컬럼 추가

## 설계
- `process_id`, `step_seq`, matrix 조회 SQL에서 불필요한 `upper(trim())` 조건을 원본 컬럼 비교로 변경한다.
- `m_tkin_prevent`에 dropdown 조회 패턴용 복합 인덱스를 추가한다.
- migration/env/auth 계약 변경은 없다.

## 실행 단계
- [x] selector SQL 변경
- [x] `m_tkin_prevent` 모델 인덱스와 신규 migration 추가
- [x] observer selector 테스트 갱신
- [x] Django 테스트와 backend boundary audit 실행

## 검증
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py test api.observer api.data_movement.m_tkin_prevent`
- `npm run agent:audit:api-boundary`
- `git diff --check`

## 위험과 대응
- 위험: 실제 데이터에 숨은 공백/소문자가 있으면 결과가 줄어들 수 있다.
- 대응: 사용자가 정규화 보장을 확인했으므로 조회 성능을 우선하고, 필요 시 적재 검증을 별도 추가한다.

## 진행 기록
- 2026-06-29: 정규화 컬럼 추가 없이 raw 컬럼 비교와 복합 인덱스로 개선하기로 결정했다.
- 2026-06-29: `upper(trim())` 제거, dropdown 조회용 복합 인덱스 추가, 관련 테스트 갱신과 검증을 완료했다.
