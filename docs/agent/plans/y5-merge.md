# ExecPlan: y5 merge

## 목표
- 최신 `origin/y5`의 L3 Spider `line_name` 변경사항을 `main`에 병합한다.
- 병합 후 L3 Spider의 LINE_NAME 선택/필터 동작이 깨지지 않고, backend/frontend boundary 규칙을 통과한다.

## 현재 상태
- 현재 브랜치: `main` (`origin/main`과 동일).
- 로컬 `y5`는 `origin/y5`보다 1커밋 뒤처져 있으므로 실제 병합 분석 기준은 `origin/y5`다.
- `origin/y5` 최신 커밋: `5e85ec8 260703: debug mail, line_name`.
- `main...origin/y5` 변경 파일:
  - `apps/api/api/l3_spider/line_name_rules.py` 추가
  - `apps/api/api/l3_spider/selectors.py`
  - `apps/api/api/l3_spider/serializers.py`
  - `apps/api/api/l3_spider/services/__init__.py`
  - `apps/web/src/features/l3-spider/hooks/useL3SpiderQueries.js`
  - `apps/web/src/features/l3-spider/utils/selection.js`
- `git merge-tree` 기준 `apps/api/api/l3_spider/services/__init__.py`에서 충돌이 난다.
- 충돌 핵심:
  - `main`: `station_master`/`drone` selector를 경유해 LINE_NAME을 생성하도록 boundary 정리 완료.
  - `origin/y5`: `_meta/line_name_rules.csv` 기반으로 `(line_id, process_id, step_seq) -> line_name`을 해석하고 `lineNames` 필터를 추가.
- `origin/y5`의 새 파일 `apps/api/api/l3_spider/line_name_rules.py`는 `apps/api/AGENTS.md`의 backend domain app 허용 파일 목록에 맞지 않는다.

## 범위
- 수정 대상:
  - L3 Spider backend selector/service/serializer
  - L3 Spider frontend selection payload/query key
  - 필요 시 L3 Spider 테스트와 최소 운영 문서
- 수정하지 않을 영역:
  - DB schema/migration
  - auth/permission
  - L3 Spider 외 도메인 로직
  - 사용자가 요청하지 않은 UI 재설계

## 설계
- 병합 대상은 로컬 `y5`가 아니라 최신 `origin/y5`로 둔다.
- `line_name_rules` 로직은 backend 허용 구조에 맞춰 `apps/api/api/l3_spider/services/line_name_rules.py`로 이동하거나, 서비스 내부의 허용된 위치로 통합한다.
- CSV 규칙 기반 LINE_NAME이 정식 소스라면:
  - `services/__init__.py`는 `line_name_rules`를 서비스 하위 모듈에서 import한다.
  - 기존 `station_master`/`drone` selector 기반 lineGroups 생성 경로는 제거하거나 fallback으로 명시적으로 분리한다.
  - `selectors.py`에는 `query_all_line_process_step()`를 추가하고, 기존 `query_all_eqcs_by_combo()` 등은 사용처 확인 후 삭제한다.
- CSV 규칙 기반 LINE_NAME이 보조 기능이라면:
  - `main`의 `station_master`/`drone` selector 기반 lineGroups를 유지한다.
  - `lineNames` 필터는 CSV 규칙으로만 적용할지, 기존 lineGroups와 매핑할지 결정한 뒤 충돌을 해소한다.
- API request contract에는 optional `lineNames`가 추가된다.
- 기존 `L3_SPIDER_DATA_ROOT/_meta/index.sqlite3`와 같은 데이터 루트 아래 `line_name_rules.csv`를 읽으므로 새 mount는 만들지 않는다. 다만 운영자가 알아야 하는 새 파일 계약이면 문서에 경로와 CSV 컬럼을 남긴다.
- migration은 예상하지 않는다.

## 실행 단계
- [x] `git fetch --all --prune` 후 `git status --short --branch`로 worktree 상태 확인
- [ ] 필요 시 `git switch -c merge/y5-line-name main`으로 병합 작업 브랜치 생성
- [x] `git merge --no-commit --no-ff origin/y5`로 충돌 상태를 만든 뒤 수동 해소
- [x] `line_name_rules`를 backend 허용 경로로 이동하고 import 경로 정리
- [x] `services/__init__.py` 충돌 해소
  - [x] `_make_selection_cache_key()`에 `lineNames` 포함
  - [x] `_filter_files_by_line_names()` 적용 위치 확인: structure/stats/data/filter-candidates
  - [x] daily summary의 line 집계 기준을 `line_name`으로 적용
  - [x] `_DAILY_SUMMARY_COLUMNS_SLIM`에 `step_seq`가 필요한 이유를 유지
- [x] `selectors.py` 충돌 해소
  - [x] `file_index` 기반 `(line_id, process_id, step_seq)` 조회 추가
  - [x] 인덱스 부재/조회 실패 시 기존 파일 스캔 폴백 유지
  - [x] 삭제 대상 selector 함수는 `rg`로 사용처 확인 후 정리
- [x] `serializers.py`에 optional `lineNames`를 추가하되 path validation 대상에서는 제외
- [x] frontend selection payload/query key에 `lineNames` 포함
- [x] L3 Spider 테스트 보강
  - [x] CSV 파일 없음: `line_id` 폴백
  - [x] exact/base/override/wildcard 우선순위
  - [x] `lineNames` 필터가 stats/data/filter-candidates에 반영
  - [x] `lineGroups`가 `file_index` 또는 기존 파일 스캔에서 생성
- [ ] 필요 시 `docs/configuration.md` 또는 L3 Spider 운영 문서에 `_meta/line_name_rules.csv` 계약 추가

## 검증
- `git diff --check`
- `npm run agent:audit:api-boundary`
- `npm run agent:audit:web-boundary`
- `npm run web:lint`
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py check`
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py makemigrations --check --dry-run`
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py test api.l3_spider --keepdb`

## 위험과 대응
- 위험: `origin/y5`의 루트 `line_name_rules.py`가 backend domain app 구조 규칙을 위반한다.
- 대응: 서비스 하위 허용 경로로 이동하고 import를 정리한 뒤 `agent:audit:api-boundary`로 확인한다.
- 위험: `main`의 selector 기반 LINE_NAME과 `origin/y5`의 CSV 규칙 기반 LINE_NAME이 서로 다른 정답을 만들 수 있다.
- 대응: 병합 실행 전 CSV 규칙 기반 LINE_NAME을 정식 소스로 채택할지 확인하고, 하나의 source of truth만 남긴다.
- 위험: `lineNames`가 cache key에 빠지면 다른 선택 결과가 재사용될 수 있다.
- 대응: backend/frontend query key와 service cache key 모두에 `lineNames`를 포함한다.
- 위험: `line_name_rules.csv`가 없거나 깨진 경우 전체 화면이 빈 값이 될 수 있다.
- 대응: 파일 없음/파싱 실패 시 `line_id` fallback 테스트를 추가한다.
- 위험: daily summary가 `line_id`에서 `line_name` 기준으로 바뀌면 기존 수치가 달라진다.
- 대응: 변경 의도를 명확히 하고, 테스트에서 headline/matrix 기준을 고정한다.

## 진행 기록
- 2026-07-03: `origin/y5` 최신 변경을 fetch하고 `main...origin/y5` 차이와 `merge-tree` 충돌을 확인했다.
- 2026-07-03: 병합 계획은 최신 `origin/y5` 기준으로 세우며, `line_name_rules` 파일 위치와 LINE_NAME source of truth 결정을 주요 위험으로 기록했다.
- 2026-07-03: `origin/y5`를 `--no-commit`으로 병합하고, `line_name_rules`를 `services/` 하위로 이동해 backend 구조 규칙에 맞췄다.
- 2026-07-03: CSV 규칙 기반 line_name을 source of truth로 적용하고, `lineNames` 필터/캐시 키/테스트를 보강했다.
- 2026-07-03: `git diff --cached --check`, `npm run agent:audit:api-boundary`, `npm run agent:audit:web-boundary`, `npm run web:lint`, `docker compose -f docker-compose.dev.yml exec -T api python manage.py check`, `docker compose -f docker-compose.dev.yml exec -T api python manage.py makemigrations --check --dry-run`, `docker compose -f docker-compose.dev.yml exec -T api python manage.py test api.l3_spider --keepdb`가 통과했다.
- 2026-07-03: `origin/y5`가 `c5086ed`로 갱신되어 추가 변경을 반영했다. daily summary의 file_index 집계 경로, Summary UI 2개 매트릭스, L3 Spider API 문서 갱신을 흡수했고, `line_name_rules`는 계속 `services/` 하위 구조로 유지했다.
- 2026-07-03: 최신 `origin/y5` 반영 후 `git diff --cached --check`, `npm run agent:audit:api-boundary`, `npm run agent:audit:web-boundary`, `npm run agent:audit:ui`, `npm run web:lint`, `docker compose -f docker-compose.dev.yml exec -T api python manage.py check`, `docker compose -f docker-compose.dev.yml exec -T api python manage.py makemigrations --check --dry-run`, `docker compose -f docker-compose.dev.yml exec -T api python manage.py test api.l3_spider --keepdb`가 통과했다.
