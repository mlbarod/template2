# ExecPlan: L3 Spider 메일링 설정

## 목표
- L3 Spider에서 사용자가 메일 알림 rule을 직접 설정할 수 있게 한다.
- 사용자는 이상 상태 조건, 문자열 패턴 필터, 수신자, 발송 주기/시각을 관리한다.
- 조회 API에는 발송 side effect를 넣지 않고 별도 trigger에서 중복 없이 메일을 발송한다.

## 현재 상태
- `api.l3_spider`는 Parquet 기반 read-only 조회와 사용자별 제외 필터 CRUD를 제공한다.
- 제외 필터는 `*`, `%` 와일드카드 패턴을 사용한다.
- 공통 메일 발송은 `api.common.services.send_knox_mail_api`로 제공된다.
- ESOP/Line Dashboard는 target/channel/recipient 설정과 발송 이력을 DB에 둔다.
- 현재 메일 본문 링크는 L3 Spider 기본 화면만 열며, 화면은 URL query를 읽어 필터를 초기화하지 않는다.

## 범위
- 수정할 영역:
  - `apps/api/api/l3_spider`
  - `apps/web/src/features/l3-spider`
  - `airflow/dags`
  - `env`, `docs`
- 수정하지 않을 영역:
  - ESOP/Drone 기존 모델과 발송 파이프라인
  - 공통 Mail API request/response contract
  - 기존 L3 Spider 조회 API의 응답 의미

## 설계
- `L3SpiderMailRule`은 사용자별 알림 rule을 저장한다.
- `L3SpiderMailDelivery`는 rule/event 단위 발송 결과를 저장하며 `rule + event_key`로 중복을 방지한다.
- `L3SpiderMailRulePermission`은 owner가 다른 사용자에게 부여한 `read`/`write` 권한을 저장한다.
- rule 필터 필드는 제외 필터와 같은 `line_id`, `process_id`, `eds_step`, `step_seq`, `ppid`, `eqpch`, `bin_name`, 날짜 범위를 사용한다.
- 심각도 조건은 `high_risk` 또는 `warning_or_high_risk`로 저장한다.
- 발송 주기는 1차로 `daily`와 `send_time`을 지원한다. Airflow는 고정 주기로 trigger를 호출하고 backend가 due rule만 처리한다.
- 수신자는 email 문자열 목록으로 저장하고 service/serializer에서 정규화한다.
- 메일 발신자는 `L3_SPIDER_MAIL_SENDER`를 사용하고, 미설정 시 `DRONE_MAIL_SENDER`를 fallback으로 사용한다.
- 메일 본문 링크는 `L3_SPIDER_MAIL_TARGET_URL`이 있으면 해당 값을 사용하고, 없으면 `FRONTEND_BASE_URL + /l3_spider`를 사용한다.
- 메일 이벤트 row 링크는 `date`, `lineId`, `processId`, `edsStep`, `stepSeq`, `ppid`, `eqpch`, `binName` query param을 붙여 특정 이벤트 조건으로 화면을 연다.
- L3 Spider 화면은 query param을 한 번만 읽어 selector/leaf filter 상태를 초기화하고, 이후 사용자의 수동 선택 변경을 보존한다.

## 실행 단계
- [x] 모델/serializer/service/view/url 추가
- [x] migration 생성
- [x] frontend API/hook/UI 추가
- [x] Airflow DAG/env/docs 동기화
- [x] read/write 공유 권한과 메일 링크 추가
- [x] 테스트 및 audit 실행
- [x] 메일 이벤트별 deep link 생성 추가
- [x] L3 Spider URL query 초기 선택 적용 추가
- [x] deep link 검증 테스트/audit 실행

## 검증
- PASS: `docker compose -f docker-compose.dev.yml exec -T api python manage.py check`
- PASS: `docker compose -f docker-compose.dev.yml exec -T api python manage.py test api.l3_spider --keepdb`
- PASS: `docker compose -f docker-compose.dev.yml exec -T api python manage.py makemigrations --check --dry-run`
- PASS: `docker compose -f docker-compose.dev.yml exec -T api python manage.py migrate l3_spider`
- PASS: `docker compose -f docker-compose.dev.yml exec -T api python manage.py test api.l3_spider --keepdb` (권한/메일 링크 추가 후 14 tests)
- PASS: `docker compose -f docker-compose.dev.yml exec -T web npm run lint`
- PASS: `docker compose -f docker-compose.dev.yml exec -T web npm run build`
- PASS: `npm run agent:audit:ui`
- PASS: `npm run agent:audit:web-boundary`
- PASS: `npm run agent:audit:docs`
- PASS: `python /app/scripts/agent/check_backend_boundaries.py` inside `api` container with temporary script copy.
- PASS: `docker compose -f docker-compose.dev.yml exec -T api python manage.py test api.l3_spider --keepdb`
- PASS: `docker compose -f docker-compose.dev.yml exec -T web npm run lint`
- PASS: `docker compose -f docker-compose.dev.yml exec -T web npm run build`
- PASS: `npm run agent:audit:ui`
- PASS: `npm run agent:audit:web-boundary`
- PASS: `npm run agent:audit:docs`
- PASS: `python /tmp/backend_audit_repo/scripts/agent/check_backend_boundaries.py` inside `api` container with temporary source copy.

## 위험과 대응
- 위험: 화면 조회 시 메일이 중복 발송될 수 있음.
- 대응: 조회 API와 발송 trigger를 분리하고 delivery unique key로 중복을 차단한다.
- 위험: 사용자별 임의 수신자 입력으로 과도한 발송이 가능함.
- 대응: serializer에서 email 형식을 검증하고 수신자 수를 제한한다.
- 위험: 사용자별 스케줄을 Airflow DAG로 직접 만들면 운영이 복잡해짐.
- 대응: 고정 주기 DAG가 backend trigger를 호출하고 backend가 due rule만 처리한다.
- 위험: query param이 실제 데이터 후보에 없으면 화면이 빈 차트 상태로 진입할 수 있음.
- 대응: URL 초기값은 기존 API 조회 경로를 그대로 사용하며, 후보가 없는 경우 기존 empty/error UI를 표시한다.

## 진행 기록
- 2026-07-01: 이전 대화 요구사항을 반영해 사용자별 rule, severity 선택, 패턴 필터, 수신자 email 목록, daily send_time, 별도 trigger 구조로 계획을 작성했다.
- 2026-07-01: L3 Spider 메일 rule/delivery, API, Airflow DAG, Web 설정 시트, env/docs, 테스트를 구현하고 검증을 통과했다.
- 2026-07-01: 메일 rule 공유 권한(read/write)과 메일 본문 L3 Spider 이동 링크를 추가하고 검증을 다시 통과했다.
- 2026-07-01: 메일 이벤트 row별 deep link와 프론트 URL query 초기 선택 적용을 추가하기로 결정했다.
- 2026-07-01: 메일 deep link, Web query 초기화, 샘플/문서를 반영하고 backend/frontend/docs/audit 검증을 통과했다.
