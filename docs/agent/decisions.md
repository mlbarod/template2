# Agent Decisions

이 문서는 반복 설명 비용을 줄이기 위한 확정 결정만 기록한다.

## 확정된 운영 결정
- 프로젝트 전용 skill은 `.codex/skills/*/SKILL.md`에 둔다.
- `.codex/skills/.system/**`은 로컬 시스템 skill로 보고 추적/공유 대상에서 제외한다.
- frontend UI 변경 후에는 `npm run agent:audit:ui` 또는 `scripts/agent/check_ui_consistency.sh`를 실행한다.
- frontend feature import/export/routing 변경 후에는 `npm run agent:audit:web-boundary` 또는 `scripts/agent/check_frontend_boundaries.sh`를 실행한다.
- backend domain boundary/import/view/selector 변경 후에는 `npm run agent:audit:api-boundary` 또는 `scripts/agent/check_backend_boundaries.py`를 실행한다.
- PR에서는 `.github/workflows/feature-guardrails.yml`의 frontend boundary, backend boundary, lint, build, backend syntax 검사를 통과해야 한다.
- AI가 feature 작업을 수행할 때는 `docs/agent/ai-feature-workflow.md`의 기본 프롬프트와 검증 절차를 따른다.
- 큰 작업은 `docs/agent/PLANS.md`의 ExecPlan 기준을 따른다.
- eval은 `docs/agent/evals/*`의 작업/성공 기준을 기준으로 누적한다.
- OIDC 개발과 운영 Compose의 외부 registry image는 `repository.samsungds.net`를 사용하고, 외부 dev Compose는 public image 이름을 유지한다.

## 보류된 결정
- multi-agent orchestration은 eval에서 병렬 검토 효과가 확인될 때까지 도입하지 않는다.

## 2026-06-19: backend boundary audit 1차 도입

- backend boundary audit은 `scripts/agent/check_backend_boundaries.py`의 AST 기반 검증으로 운영한다.
- 1차 실패 기준은 cross-domain internal import, test cross-domain internal import, `views.py` 직접 ORM, `selectors.py` write ORM, backend app 구조 위반이다.
- 기존 service direct read ORM 후보는 범위가 넓어 CI 실패 기준에 넣지 않고 별도 debt로 관리한다.
- CI backend job은 boundary audit 후 Python compile을 실행한다.

## 2026-05-17: 앱 문서 상세화 구조

- 문서 홈은 `docs/README.md`로 유지하고, 실제 route/model/env/command 색인은 `docs/inventory.md`로 분리한다.
- 주제별 상세 문서는 `docs/backend.md`, `docs/frontend.md`, `docs/data-model.md`, `docs/configuration.md`로 분리해 문서가 길어져도 읽기 흐름을 유지한다.
- 모듈 문서는 업무 흐름과 운영 포인트를 담당하고, API 문서는 endpoint 계약을 담당한다.
- 문서 drift를 줄이기 위해 `scripts/agent/check_docs_inventory.sh`로 backend endpoint, frontend route, model, command, env group의 문서 반영 여부를 검증한다.

## 2026-05-29: data_movement 테이블별 중첩 앱 구조

- 파일 기반 DB 적재 기능은 `apps/api/api/data_movement/<table_name>` 아래에 테이블별 Django app으로 둔다.
- `<table_name>` 폴더명은 실제 target table 이름과 일치시킨다.
- 테이블별 app은 자기 model, migration, loader service, tests, management command만 소유한다.
- 공통 파일 탐색, deflate CSV 파싱, PostgreSQL COPY 유틸은 `apps/api/api/data_movement/common`에 둔다.
