# ExecPlan: L3 Spider SQLite/PostgreSQL 벤치마크

## 목표
- 대시보드 서버의 실제 SQLite mount와 Django PostgreSQL 연결을 사용해 동일 쿼리 성능을 비교한다.
- 대시보드가 실제 사용하는 Meta, Summary, Trend, 실행 통계 쿼리를 측정한다.
- 별도 관리 명령이나 보조 모듈 없이 Python 파일 하나만 실행한다.

## 현재 상태
- SQLite 경로는 `L3_SPIDER_DATA_ROOT/_meta/index.sqlite3`이다.
- PostgreSQL 연결은 Django `DATABASES["default"]`가 소유한다.
- PostgreSQL에는 복제 대상 3개 테이블이 아직 없다.

## 범위
- `apps/api/cell_benchmark_sqlite_vs_postgres.py` 단일 실행 파일을 추가한다.
- PostgreSQL 테이블 생성, 데이터 복제, 운영 schema 변경은 수행하지 않는다.
- 기존 API 조회 경로는 변경하지 않는다.

## 설계
- 실행 파일 내부에서 Django를 초기화하고 기존 settings/selectors를 통해 연결 정보를 읽는다.
- SQLite는 대시보드와 동일한 read-only URI와 10초 timeout을 사용한다.
- PostgreSQL은 Django connection alias와 schema 옵션을 사용한다.
- 첫 실행과 이후 반복 중앙값을 분리하고 결과 행 수/내용 일치 여부를 표시한다.
- 실제 cold cache 보장은 하지 않으며 첫 실행 값이라는 점을 출력한다.

## 실행 단계
- [x] 단일 Python 실행 파일 및 실제 쿼리 정의
- [x] 테이블/schema 검증과 결과 비교 구현
- [x] 기존 L3 Spider 테스트 및 백엔드 경계 검사
- [x] 로컬 실행으로 경로·오류 메시지 검증

## 검증
- `docker compose exec -T api python -m py_compile cell_benchmark_sqlite_vs_postgres.py`
- `docker compose exec -T api python cell_benchmark_sqlite_vs_postgres.py --help`
- `docker compose exec -T api python cell_benchmark_sqlite_vs_postgres.py`
- `docker compose exec -T api python manage.py test api.l3_spider --keepdb`
- `docker run --rm --entrypoint python -v /home/k/template2:/workspace -w /workspace template2-api scripts/agent/check_backend_boundaries.py`

## 위험과 대응
- 위험: PostgreSQL 복제 데이터가 SQLite와 다르면 속도 비교가 무의미하다.
- 대응: 각 쿼리 결과의 행 수와 정규화된 digest를 비교해 불일치를 경고한다.
- 위험: 첫 실행이 실제 disk cold 상태가 아닐 수 있다.
- 대응: 출력에서 `cold` 대신 `first`로 구분하고 한계를 명시한다.

## 진행 기록
- 2026-07-11: 실제 저장소 경로와 DB 설정 확인, 구현 시작.
- 2026-07-11: L3 Spider 테스트 23개와 백엔드 경계 검사 통과.
- 2026-07-11: 실제 SQLite 경로를 확인하고 PostgreSQL 복제 테이블 미생성 오류를 검증.
- 2026-07-11: 사용자 요청에 따라 관리 명령을 제거하고 단일 Python 실행 파일로 변경.
- 2026-07-11: 단일 파일 문법/도움말 검증, L3 Spider 테스트 20개와 백엔드 경계 검사 통과.
