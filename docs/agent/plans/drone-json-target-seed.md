# ExecPlan: Drone JSON Target Seed

## 목표
- `department`, `line`, `user_sdwt_prod`만 담긴 JSON 파일로 Drone SOP 알림 초기 설정을 생성한다.
- mapping, channel config, needtosend rule, account user/external snapshot 기반 recipients는 자동 생성한다.

## 현재 상태
- `seed_drone_affiliation_notifications`는 `account_affiliation` 목록을 source로 사용한다.
- 실제 생성 로직은 `apps/api/api/drone/services/channels/affiliation_seed.py`에 집중되어 있다.
- seed 실행 시 기존 Drone SOP/발송 이력/알림 설정을 초기화한 뒤 source row 기준으로 다시 만든다.

## 범위
- 수정: Drone channel seed service, service facade, management command, tests.
- 제외: DB schema/migration 변경, UI 변경, account 도메인 변경.

## 설계
- 공통 seed 함수는 `department`, `line_id`, `user_sdwt_prod` row 목록을 입력받는다.
- 공통 seed 함수는 `drone_sop`, delivery, dispatch, `drone_sop_target`, mapping,
  channel config, needtosend rule, recipient 설정을 먼저 삭제한다.
- 기존 account-affiliation seed는 account selector에서 row를 만든 뒤 공통 함수로 위임한다.
- 새 JSON command는 파일을 파싱해 같은 row 형태로 변환한 뒤 공통 함수로 위임한다.
- recipients 생성은 기존 `account_selectors.list_active_user_pool()`을 사용하되 JSON의 `department`와 `user_sdwt_prod`를 필터로 전달한다.
- migration/env/auth 변경 없음.

## 실행 단계
- [x] 공통 row 기반 seed 함수 추가
- [x] JSON 파일 seed command 추가
- [x] facade export 추가
- [x] service/command 테스트 추가
- [x] Docker Compose api 컨테이너에서 관련 테스트 실행

## 검증
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py test api.drone.tests.DroneSopAffiliationNotificationSeedTests --keepdb`
- 기대 결과: 관련 seed 테스트 통과

## 위험과 대응
- 위험: 기존 account-affiliation seed 동작이 바뀔 수 있음
- 대응: 기존 테스트를 유지하고 새 JSON path 테스트를 같은 테스트 클래스에 추가한다.
- 위험: JSON 형식 오류가 조용히 무시될 수 있음
- 대응: command에서 명확한 `CommandError`를 발생시킨다.

## 진행 기록
- 2026-05-22: JSON target seed 요구사항을 반영해 계획 작성.
- 2026-05-22: JSON seed command와 공통 row 기반 seed 함수 추가, `api.drone` 테스트 통과.
- 2026-05-22: seed 동작을 누락분 생성에서 알림 설정 초기화 후 재생성으로 변경.
- 2026-05-22: seed 초기화 범위에 `drone_sop`, `drone_sop_target_dispatch`, `drone_sop_delivery` 포함.
