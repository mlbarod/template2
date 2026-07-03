# ExecPlan: y5 브랜치 main 병합

## 목표
- `y5` 브랜치의 최신 변경사항을 `main` 브랜치에 일반 merge로 병합한다.
- 병합 후 `l3_spider` 외 다른 feature에 의도치 않은 영향이 없는지 확인한다.
- 필요한 검증이 통과하면 `main`을 원격에 push한다.

## 현재 상태
- 현재 브랜치: `main`
- `main` 최신 커밋: `64aa699 [api][agent] fix: Tkin matrix line별 셀 분리`
- `y5` 최신 커밋: `8b6d1af 260703: debuggg`
- `main`과 `y5`는 diverged 상태라 fast-forward가 아니라 merge commit이 필요하다.
- `main...y5` 변경 파일은 `apps/api/api/l3_spider/**`와 `apps/web/src/features/l3-spider/**`로 제한되어 있다.

## 범위
- 수정할 영역
  - `apps/api/api/l3_spider` 모델, serializer, selector, service, migration 병합 결과
  - `apps/web/src/features/l3-spider/components` 컴포넌트 병합 결과
  - 이 병합 작업을 추적하는 ExecPlan 문서
- 수정하지 않을 영역
  - `l3_spider` 외 feature의 기능 변경
  - auth/RAG/assistant/mail/env contract 변경
  - 요청 범위 밖 리팩터링

## 설계
- 데이터 흐름
  - `y5`의 L3 Spider mail rule schema/service/frontend 변경을 `main`의 최신 구조 위에 병합한다.
- public API/facade 영향
  - 현재 확인된 변경은 feature 내부 backend/frontend 파일이며 frontend public facade 변경은 없다.
- migration/env/auth 영향
  - `l3_spider` migration 추가가 포함된다.
  - env/auth contract 변경은 현재 범위에 없다.

## 실행 단계
- [x] `origin`, `main`, `y5` 최신 상태 확인
- [x] `main`에 `y5` 일반 merge 실행
- [x] 충돌 발생 시 `l3_spider` 범위에서 해결
- [x] 병합 결과 변경 파일과 migration graph 확인
- [x] backend/frontend 검증 실행
- [ ] 검증 통과 시 `main` push

## 검증
- `npm run agent:audit:api-boundary`
- `npm run agent:audit:web-boundary`
- `npm run agent:audit:ui`
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py test api.l3_spider`
- 필요 시 `docker compose -f docker-compose.dev.yml exec -T api python manage.py showmigrations l3_spider`

## 위험과 대응
- 위험: migration 번호 충돌 또는 이미 적용된 migration 수정 위험
- 대응: 병합 후 `apps/api/api/l3_spider/migrations` 상태와 Django migration graph를 확인한다.
- 위험: `main`의 최신 L3 Spider 변경과 `y5`의 오래된 변경이 충돌할 수 있다.
- 대응: conflict marker를 제거하고 현재 `main` 구조를 기준으로 필요한 `y5` 변경만 반영한다.
- 위험: frontend UI 변경이 다른 feature import boundary를 건드릴 수 있다.
- 대응: 변경 파일 범위를 확인하고 web boundary audit을 실행한다.

## 진행 기록
- 2026-07-03: `main...y5` 변경 범위가 L3 Spider backend/frontend 파일로 제한됨을 확인하고 병합 계획을 작성했다.
- 2026-07-03: `apps/api/api/l3_spider/services/__init__.py` 충돌을 해결하고 `date_from` 제거, 오늘 날짜 기준 mail rule 수집, `procEds` lineGroups 응답을 병합했다.
- 2026-07-03: `api.l3_spider` 테스트 기대값을 병합된 계약에 맞게 갱신했다.
- 2026-07-03: `npm run agent:audit:api-boundary`, `npm run agent:audit:web-boundary`, `npm run agent:audit:ui`, `npm run web:lint`, `docker compose -f docker-compose.dev.yml exec -T api python manage.py test api.l3_spider --keepdb`, `makemigrations --check --dry-run`, `showmigrations l3_spider` 검증을 완료했다.
