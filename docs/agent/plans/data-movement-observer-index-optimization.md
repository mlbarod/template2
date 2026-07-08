# ExecPlan: Data Movement and Observer index optimization

## 목표
- Observer와 Data Movement의 주요 조회, 조인, 정렬 쿼리에 맞는 보수적 DB 인덱스를 추가한다.
- `ct_process_comment` 요약 배치, CTTTM workorder 설명/조인, 예방보전 matrix 조회의 병목 가능성을 낮춘다.

## 현재 상태
- `ct_process_comment` 요약 대상 조회는 `update_flag='Y'`와 `updated_at desc, id desc` 정렬을 사용하지만 대응 인덱스가 없다.
- `ctttm_workorder_list`는 Observer timeline용 `eqp_id_lookup, -inprg_date` 인덱스는 있으나 `workorder_id` 기반 설명 조회와 comment loader의 `EXISTS` 조인을 받치는 인덱스가 없다.
- `m_tkin_prevent`는 Observer matrix가 `line_id`, `eqp_id`, `process_id` 조합으로 자주 필터/정렬하지만 해당 순서의 복합 인덱스가 없다.

## 범위
- 수정: 관련 Data Movement 모델의 `Meta.indexes`, 신규 migration, 필요한 selector projection.
- 수정하지 않음: API contract, 응답 shape, 기존 business logic, 기존 인덱스 제거.

## 설계
- `ct_process_comment`: pending 요약 대상만 담는 partial index를 추가하고, selector는 요약 배치에 필요한 컬럼만 조회한다.
- `ctttm_workorder_list`: `workorder_id, -inprg_date, -id` 복합 인덱스를 추가해 workorder 설명 조회와 join existence check를 보조한다.
- `m_tkin_prevent`: `line_id, eqp_id, process_id, step_seq` 복합 인덱스를 추가해 Observer의 target equipment join 이후 process/step 조회를 보조한다.
- migration/env/auth/API contract 영향은 없고 DB index schema만 추가된다.

## 실행 단계
- [x] 관련 모델과 selector 수정
- [x] 신규 migration 추가
- [x] migration 생성 누락 여부 확인
- [x] 관련 backend 테스트 및 boundary audit 실행

## 검증
- 통과: `docker compose -f docker-compose.dev.yml exec -T api python manage.py makemigrations --check --dry-run`
- 통과: `docker compose -f docker-compose.dev.yml exec -T api python manage.py test api.data_movement.ct_process_comment api.data_movement.ctttm_workorder_list api.data_movement.m_tkin_prevent api.observer --keepdb`
- 통과: `npm run agent:audit:api-boundary`

## 위험과 대응
- 위험: 인덱스 추가로 적재/upsert 쓰기 비용과 storage가 증가할 수 있다.
- 대응: 운영 사용량 통계 없이 기존 인덱스 제거는 하지 않고, 실제 쿼리 패턴과 직접 대응되는 인덱스만 추가한다.

## 진행 기록
- 2026-07-07: 쿼리 패턴을 검토하고 보수적 추가 인덱스 후보를 선정했다.
- 2026-07-07: `ct_process_comment`, `ctttm_workorder_list`, `m_tkin_prevent` 인덱스와 migration을 추가하고 관련 검증을 통과했다.
