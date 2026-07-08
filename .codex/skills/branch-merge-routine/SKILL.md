---
name: branch-merge-routine
description: Merge a source branch into `main` or another target branch with repository boundary checks, cross-feature impact review, validation, and optional push. Use when the user asks to merge, reflect, sync, or push branch changes, especially wording such as "y5 변경사항 merge", "feature 브랜치 main 반영", "이 브랜치 메인에 푸시", or "브랜치 병합 루틴".
---

# branch-merge-routine

## 목적
source branch 변경사항을 target branch에 반영할 때 변경 의도를 최대한 보존하되, 다른 feature/app/API/공개 파사드 훼손 여부를 먼저 확인한다.

## 기본 원칙
- 항상 `request-intake-gate`를 먼저 적용한다.
- source branch를 사용자 요청에서 식별한다. 명확하지 않으면 Hard-Block으로 묻는다.
- target branch는 명시가 없으면 `main`으로 본다.
- 현재 브랜치가 target branch인지 확인한다. 아니면 사용자에게 현재 브랜치와 진행 의도를 짧게 확인한다.
- 병합 대상은 최신 `origin/<source_branch>`를 기본으로 한다.
- source branch 변경은 기본적으로 존중한다. 단, 다른 앱을 깨거나 기존 공개 contract를 훼손할 가능성이 있으면 자동으로 덮어쓰지 않고 원인과 선택지를 보고한다.
- 사용자가 명시적으로 push를 요청한 경우에만 `origin/<target_branch>`에 push한다.
- 자동 commit은 push/PR/릴리즈 finalization 요청이 있거나, 검증 통과 후 push를 위해 필요한 경우에만 한다.

## 절차
1. 상태 확인
   - `git status --short --branch`
   - `git fetch origin <source_branch>`
   - `git branch -vv --list <target_branch> <source_branch>`
   - dirty worktree가 있으면 변경 파일이 이번 요청과 무관한지 확인하고, 무관한 변경은 건드리지 않는다.

2. 영향도 확인
   - `git diff --stat <target_branch>...origin/<source_branch>`
   - `git diff --name-only <target_branch>...origin/<source_branch>`
   - 변경 파일을 feature/app/domain별로 분류한다.
   - 여러 feature, `apps/api`, `compose`, `env`, `AGENTS.md`, `.codex/skills`, public facade, route, auth, DB migration, API schema가 포함되면 관련 scoped `AGENTS.md`와 skill을 추가로 읽고 검증 계획을 세운다.
   - 변경 파일이 한 feature 내부에만 있더라도 import/export, route, shared component, API 호출을 통해 다른 feature에 영향을 줄 수 있는지 확인한다.

3. 병합
   - 기본 명령은 `git merge --no-edit origin/<source_branch>`이다.
   - 충돌이 없으면 다음 단계로 진행한다.
   - 충돌이 있으면 파일별로 의도를 읽고 해결한다.
   - 충돌 해결 기준은 source branch 의도를 우선하되, 다른 앱/feature의 현재 동작과 공개 contract를 보존하는 것이다.
   - 둘 다 만족할 수 없으면 사용자에게 Hard-Block으로 묻는다.

4. 병합 후 점검
   - `git status --short --branch`
   - 병합 결과 diff와 변경 파일을 다시 확인한다.
   - 다른 feature 영향 후보가 있으면 해당 경로의 facade/import/route/API 사용처를 `rg`로 추적한다.
   - 불필요한 리팩터링을 추가하지 않는다.

5. 검증
   - `apps/web` 변경이 있으면 `cd apps/web && npm run lint`를 기본 검증으로 실행한다.
   - `apps/api` 변경이 있으면 Docker Compose `api` 컨테이너 기준으로 관련 테스트/마이그레이션 검증을 실행한다.
   - agent rule/skill/script 변경이 있으면 skill validator 또는 해당 validation command를 실행한다.
   - 검증 실패가 병합된 파일의 좁은 문제이면 최소 수정으로 고친다. 범위가 다른 앱/feature로 확장되면 멈추고 보고한다.

6. commit/push
   - 사용자가 merge만 요청했으면 push하지 않는다.
   - 사용자가 push를 요청했고 미커밋 수정이 필요하면 현재 요청에서 만든 변경만 stage한다.
   - commit message는 AGENTS.md 규칙을 따른다. 예: `[l3-spider][web] fix: y5 병합 lint 오류 정리`
   - `git push origin <target_branch>` 후 `git status --short --branch`와 최근 log를 확인한다.

## 보고 형식
- 병합 전에는 변경 파일 수, 영향 feature/app, Hard-Block 여부를 짧게 알린다.
- 병합 후에는 충돌 여부, 추가 수정 여부, 실행한 검증과 결과를 보고한다.
- push 후에는 원격 반영 커밋과 작업트리 상태를 보고한다.
