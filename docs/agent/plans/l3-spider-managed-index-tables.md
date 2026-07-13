# ExecPlan: L3 Spider 인덱스 테이블 Django 관리 전환

## 목표
- `public.l3_spider_file_index`, `public.l3_spider_daily_run_stats`,
  `public.l3_spider_run_status`를 Django 모델과 migration이 관리하게 한다.
- 기존 운영 테이블과 데이터를 유지하면서 신규 환경에도 동일한 스키마를 생성한다.

## 현재 상태
- API selector는 세 테이블을 기본 PostgreSQL 연결에서 raw SQL로 읽는다.
- 세 테이블은 알고리즘 서버가 적재하지만 현재 Django 모델과 migration에는 없다.
- 로컬 개발 DB에는 세 테이블이 아직 없고, Django 관리 L3 Spider 테이블만 존재한다.
- `daily_run_stats`는 5개 컬럼으로 구성된 복합 PK를 사용한다.

## 범위
- 수정: L3 Spider 모델, 신규 migration, 모델/migration 회귀 테스트, backend dependency 하한.
- 수정: L3 Spider 모델 inventory 문서.
- 유지: 기존 selector SQL, API 응답 계약, 알고리즘 서버의 적재 방식.
- 제외: 기존 데이터 변환, 컬럼 타입 변경, selector ORM 전환.

## 설계
- Django 5.2 `CompositePrimaryKey`로 `daily_run_stats`의 복합 PK를 표현한다.
- 제공된 테이블명, 컬럼 타입, null/default, PK와 인덱스 이름을 그대로 모델에 반영한다.
- migration은 `CREATE TABLE/INDEX IF NOT EXISTS`로 기존 테이블을 인수하고 신규 환경에는 생성한다.
- migration 적용 중 실제 컬럼, null/default, PK, 인덱스가 계약과 다르면 명확하게 실패시킨다.
- reverse migration은 Django가 관리하는 세 테이블을 의존성 역순으로 제거한다.

## 실행 단계
- [x] 모델과 Django 버전 하한 추가
- [x] 기존 테이블 인수형 migration과 스키마 검증 추가
- [x] 모델 메타데이터 및 migration 회귀 테스트 추가
- [x] inventory 문서 갱신
- [x] Docker Compose `api` 컨테이너에서 migration과 테스트 검증

## 검증
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py makemigrations --check --dry-run`
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py migrate l3_spider`
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py test api.l3_spider --keepdb -v 1`
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py check`
- `npm run agent:audit:api-boundary`
- `git diff --check`

## 위험과 대응
- 위험: 운영 테이블이 제공된 DDL과 다르지만 migration이 적용된 것으로 기록될 수 있다.
- 대응: 인수 직후 `information_schema`와 PostgreSQL catalog를 검증하고 불일치 시 실패한다.
- 위험: Django 5.1에는 복합 PK 모델 지원이 없다.
- 대응: backend Django 하한을 5.2로 올린다.
- 위험: reverse migration 시 기존 운영 데이터가 삭제될 수 있다.
- 대응: reverse 실행은 명시적 rollback으로 한정하고 세 테이블이 삭제됨을 migration에 드러낸다.

## 진행 기록
- 2026-07-13: 사용자 제공 PostgreSQL DDL 3종과 기존 데이터 보존 인수 방식을 확정했다.
- 2026-07-13: Django 5.2 managed 모델 3종과 `0005_manage_index_tables` migration을 추가했다.
- 2026-07-13: 로컬 dev DB migration 적용, 실제 스키마 대조, 기존 행 보존 테스트를 완료했다.
- 2026-07-13: L3 Spider 테스트 36개, Django check/migration check, backend boundary audit, diff check가 통과했다.
