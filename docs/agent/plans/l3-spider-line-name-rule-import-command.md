# ExecPlan: L3 Spider line name rule CSV import command

## 목표
- 서버의 `line_name_rules.csv`를 `L3SpiderLineNameRule` 모델에 적재하는 Django management command를 제공한다.
- CSV 규칙 순서와 wildcard 의미를 DB 필드로 보존한다.

## 현재 상태
- 현재 브랜치에는 `L3SpiderLineNameRule` 모델이 없어 command와 함께 추가해야 한다.
- CSV는 `{L3_SPIDER_DATA_ROOT}/_meta/line_name_rules.csv`에 있고 `type,line_id,process_id,step_seq,line_name` 컬럼을 사용한다.
- 실제 적재는 사용자가 서버에서 실행한다.

## 범위
- 추가: `L3SpiderLineNameRule` 모델/migration, management command, DB resolver 전환과 테스트.
- 제외: 운영 데이터 자동 이관.

## 설계
- command 이름은 `import_l3_spider_line_name_rules`로 한다.
- 기본 경로는 L3 Spider 데이터 루트의 `_meta/line_name_rules.csv`이며 `--path`로 덮어쓸 수 있다.
- 기본 동작은 활성 동일 key를 갱신하고 다른 DB 규칙은 보존한다.
- `--replace`는 transaction 안에서 기존 행 전체를 지운 뒤 CSV 규칙을 생성한다.
- `--dry-run`은 CSV와 대상 모델 계약만 검증하고 DB를 변경하지 않는다.
- 빈 값, `%`, `*` wildcard는 `*`로 정규화하며 CSV 유효 행 순서를 `priority`로 저장한다.
- 런타임 resolver는 활성 DB 규칙을 `priority`, `id` 순으로 읽고 5초 TTL로 갱신한다.
- 규칙이 없으면 기존과 동일하게 `line_name = line_id`로 폴백한다.

## 실행 단계
- [x] management package와 import command 추가
- [x] parser와 command option 테스트 추가
- [x] `L3SpiderLineNameRule` 모델과 migration 추가
- [x] 실제 모델 기반 command DB 테스트 추가
- [x] CSV runtime resolver를 DB selector 기반으로 전환
- [x] Docker Compose `api` 기준 정적/테스트 검증

## 검증
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py test api.l3_spider.tests.L3SpiderLineNameRuleImportCommandTests --keepdb -v 1`
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py check`
- `npm run agent:audit:api-boundary`
- `git diff --check`

## 위험과 대응
- 위험: CSV의 대소문자 차이로 동일한 활성 규칙이 중복될 수 있다.
- 대응: PostgreSQL functional unique constraint와 case-insensitive upsert를 함께 적용한다.
- 위험: `--replace`가 기존 DB 규칙을 삭제한다.
- 대응: 명시적 옵션에서만 실행하고 전체 과정을 `transaction.atomic()`으로 보호한다.

## 진행 기록
- 2026-07-13: 사용자가 대상 서버에서 직접 실행하며 모델/migration과 dev DB 적재는 범위에서 제외한다고 확정했다.
- 2026-07-13: `import_l3_spider_line_name_rules` command와 parser 테스트 4개를 추가했다.
- 2026-07-13: L3 Spider 테스트 40개, Django check, backend boundary audit, diff check가 통과했다.
- 2026-07-13: main에 대상 모델이 없음을 확인한 뒤 사용자 요청으로 모델과 migration을 범위에 포함했다.
- 2026-07-13: 모델/migration, DB selector, 5초 TTL resolver와 실제 command DB 테스트를 반영했다.
- 2026-07-13: L3 Spider 테스트 43개, 전체 web lint, Django/migration check, backend/frontend boundary audit가 통과했다.
