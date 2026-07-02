# ExecPlan: L3 Spider selector boundary

## 목표
- L3 Spider가 `station_master`, `drone` 모델을 직접 import하지 않고 각 앱의 selector를 통해 read-only 데이터를 조회하도록 정리한다.

## 현재 상태
- `apps/api/api/l3_spider/services/__init__.py`의 lineGroups 생성 로직이 `StationMaster`, `DroneSopTarget` 모델을 직접 import한다.
- `npm run agent:audit:api-boundary`가 이 두 import를 cross-domain 내부 import 후보로 보고한다.
- 기존 앱들은 `observer`, `account`, `drone`처럼 다른 도메인 조회를 selector alias로 처리한다.

## 범위
- 수정 대상:
  - `apps/api/api/data_movement/station_master/selectors.py`
  - `apps/api/api/drone/selectors.py`
  - `apps/api/api/l3_spider/services/__init__.py`
- 수정하지 않을 영역:
  - DB schema/migration
  - API request/response contract
  - 프론트엔드 UI
  - L3 Spider 집계 알고리즘의 의미 변경

## 설계
- `station_master` selector가 EQC/station lookup 목록을 받아 `station_lookup -> sdwt_prod_lookup` 매핑을 반환한다.
- `drone` selector가 `target_user_sdwt_prod -> line_id` 매핑을 반환한다.
- L3 Spider 서비스는 두 selector 결과와 기존 `eqp_index` 결과만 조합한다.
- public API/facade, auth, env, migration 영향은 없다.

## 실행 단계
- [x] `station_master` selector에 매핑 조회 함수 추가
- [x] `drone` selector에 target 매핑 조회 함수 추가
- [x] L3 Spider 서비스의 직접 모델 import 제거 및 selector 호출로 교체
- [x] backend boundary audit와 관련 테스트 실행

## 검증
- `npm run agent:audit:api-boundary` 통과
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py check` 통과
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py test api.l3_spider --keepdb` 통과

## 위험과 대응
- 위험: 매핑 정규화 방식이 기존 결과와 달라질 수 있다.
- 대응: 기존 호출부의 대문자 key 조회 방식에 맞춰 selector 반환 key만 대문자로 정규화하고, 값은 기존 표시값을 유지한다.

## 진행 기록
- 2026-07-02: L3 Spider cross-domain model import를 selector 경유로 정리하기로 결정.
- 2026-07-02: `station_master`, `drone` selector를 추가하고 L3 Spider 서비스의 직접 모델 import를 제거함.
