# ExecPlan: PR 16 Main Merge Fix

## 목표
- PR #16 변경분을 로컬 `main`에 병합 후보 상태로 가져온다.
- 기존 GitHub Actions 실패 원인을 수정한다.
- 검증 통과 후 사용자가 `main`에 push할 수 있는 상태로 만든다.

## 현재 상태
- 열린 PR #16은 `claude4gae:main`에서 `pjw7536:main`으로 들어온다.
- GitHub는 충돌 없음(`mergeable=true`)으로 보고하지만 checks는 실패 상태다.
- 실패 원인은 backend view 직접 ORM 사용과 frontend lint 위반으로 확인됐다.
- PR 변경분은 로컬 `main`에 `--no-commit`으로 병합되어 있고, 실패 지점 수정과 검증이 완료됐다.

## 범위
- 수정할 영역:
  - `apps/api/api/l3_spider`의 제외 필터 view/service 책임 분리
  - `apps/web/src/features/l3-spider`의 lint 실패 지점
- 수정하지 않는 영역:
  - PR #16의 기능 설계 전체 재작성
  - unrelated app/refactor
  - 원격 `main` push

## 설계
- `git merge --no-commit`으로 PR 변경분을 `main`에 얹고 검증 전 commit을 만들지 않는다.
- view의 ORM read/write는 `services` 함수로 이동해 backend boundary audit을 통과시킨다.
- frontend lint 실패는 최소 수정으로 해결한다.
- PR #16에 포함된 migration/API surface는 유지한다.

## 실행 단계
- [x] PR #16 fetch 및 `main`에 no-commit merge
- [x] backend boundary 실패 수정
- [x] frontend lint 실패 수정
- [x] backend/frontend guardrail 및 build 검증
- [x] 최종 상태와 push 절차 보고

## 검증
- `python3 scripts/agent/check_backend_boundaries.py`
- `python3 -m compileall -q apps/api`
- `npm run agent:audit:web-boundary`
- `npm run web:lint`
- `npm run web:build`

## 위험과 대응
- 위험: PR #16이 큰 변경이라 검증 중 추가 실패가 나올 수 있다.
- 대응: CI에서 이미 확인된 실패를 먼저 고치고, 추가 실패는 범위 내에서 최소 수정한다.

## 진행 기록
- 2026-06-29: PR #16을 로컬 `main`에 병합 후보로 가져와 CI 실패를 수정하는 계획을 작성했다.
- 2026-06-29: 제외 필터 CRUD ORM 접근을 service로 이동하고 frontend lint 실패를 수정했다.
- 2026-06-29: `api.pm_comparison`, `api.l3_spider` 테스트와 backend/frontend guardrail, web lint/build 검증이 통과했다.
