# ExecPlan: L3 Spider PostgreSQL 전용 전환

## 목표
- L3 Spider의 인덱스/실행 상태 조회를 SQLite에서 PostgreSQL `public` schema로 전환한다.
- 이상 없음 라인도 `daily_run_stats`를 기준으로 분석 `step_seq` 수를 표시한다.

## 현재 상태
- Meta, Summary, Trend, 파일 조회가 `_meta/index.sqlite3`의 세 테이블을 읽는다.
- `file_index`는 이상 없음 라인의 분석 조합을 포함하지 않을 수 있다.
- 운영 PostgreSQL은 알고리즘 서버가 세 테이블을 지속 적재하고 마지막에 `completed`를 기록한다.

## 범위
- `public.l3_spider_file_index`, `public.l3_spider_daily_run_stats`,
  `public.l3_spider_run_status` read selector를 PostgreSQL로 변경한다.
- SQLite 연결과 SQLite fallback을 제거한다.
- Parquet 원본 파일 읽기는 기존 NFS mount를 유지한다.
- 외부 적재 테이블을 Django migration으로 생성하거나 수정하지 않는다.

## 설계
- Django `DATABASES["default"]` 연결과 parameterized SQL을 사용한다.
- PostgreSQL 장애나 테이블 누락은 빈 결과로 숨기지 않고 실패시킨다.
- 기존 `runStats.byLine` 계약은 유지하고 상세 실행 통계로 `runStats.byLineName`을 계산한다.
- 사용자 제외 필터의 경로 필드는 `daily_run_stats` 상세 행에도 적용한다.

## 실행 단계
- [x] PostgreSQL 공통 조회 helper와 file_index selector 전환
- [x] run_status, Trend, daily_run_stats selector 전환
- [x] `daily_run_stats` 기반 line_name 집계 수정
- [x] selector/service 회귀 테스트 추가 및 기존 테스트 격리
- [x] 전체 L3 Spider 테스트와 경계 검사

## 검증
- `docker compose exec -T api python manage.py test api.l3_spider --keepdb -v 1`
- `docker run --rm --entrypoint python -v /home/k/template2:/workspace -w /workspace template2-api scripts/agent/check_backend_boundaries.py`
- PostgreSQL 테이블 미적재 개발 환경에서 명확한 오류 확인
- `git diff --check`

## 위험과 대응
- 위험: 운영 PostgreSQL 컬럼 타입이 SQLite와 다를 수 있다.
- 대응: 날짜는 문자열로 정규화하고 JSON/JSONB 배열을 모두 수용하는 조회식을 사용한다.
- 위험: PostgreSQL 적재 지연 중 부분 날짜가 노출될 수 있다.
- 대응: `run_status.status='completed'` 날짜만 기존과 동일하게 노출한다.
- 위험: PostgreSQL 장애 시 L3 Spider 전체 조회가 실패한다.
- 대응: 사용자가 PostgreSQL 전용을 선택했으므로 의도적으로 fallback하지 않고 오류를 노출한다.

## 진행 기록
- 2026-07-13: 운영 schema=`public`, 알고리즘 서버 지속 적재/완료 마커 계약 확인.
- 2026-07-13: PostgreSQL 전용 전환 구현 시작.
- 2026-07-13: L3 Spider 테스트 24개, backend boundary audit, migration check 통과.
- 2026-07-13: 외부 테이블 미적재 환경에서 PostgreSQL 오류가 그대로 노출되어 SQLite fallback이 없음을 확인.
- 2026-07-13: 외부 테이블명을 `l3_spider_*`로 변경.
