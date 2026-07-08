# AGENTS.md

## 0. Purpose
This repository is a modular monolith with strict frontend/backend boundaries.
`AGENTS.md` contains only always-on core constraints.
Detailed execution workflows are delegated to `.codex/skills/*`.

## 0-1. Rule Priority
1. Direct user instruction
2. This AGENTS.md
3. Feature-local public facade contracts
4. Existing file conventions that do not conflict with rules above

## 0-2. Core vs Workflow
- Keep architecture/boundary constraints in this file.
- Move step-by-step procedures, templates, and command playbooks to skills.
- When a request matches a workflow category, use the matching skill first.

## 0-3. Skill Routing (Required)
- Request intake gate: `.codex/skills/request-intake-gate/SKILL.md`
- New Django feature scaffold: `.codex/skills/create-django-feature/SKILL.md`
- Django tests + migrations flow: `.codex/skills/django-test-migration-flow/SKILL.md`
- Backend boundary audit: `.codex/skills/backend-boundary-audit/SKILL.md`
- Korean-commented Python output: `.codex/skills/write-commented-python/SKILL.md`
- Frontend layout composition: `.codex/skills/compose-frontend-layout/SKILL.md`
- Product UI design system: `.codex/skills/product-ui-design-system/SKILL.md`
- UI consistency audit: `.codex/skills/ui-consistency-audit/SKILL.md`
- Frontend boundary audit: `.codex/skills/frontend-boundary-audit/SKILL.md`
- Safe file edit/output format: `.codex/skills/safe-file-edit-output/SKILL.md`
- Offsite contract synchronization: `.codex/skills/offsite-dev-contract-sync/SKILL.md`
- Branch merge routine: `.codex/skills/branch-merge-routine/SKILL.md`

## 0-4. Planning and Evaluation
- For complex changes, use `docs/agent/PLANS.md`.
- Use an ExecPlan when work changes 3+ files, touches API/DB/auth/env contracts, spans frontend and backend, or is a significant refactor.
- Do not use ExecPlan for small single-file fixes, obvious typo/import cleanup, or tightly specified edits.
- Use `docs/agent/evals/*` as regression seeds for common agent tasks.
- After changing agent rules/skills/scripts, run the relevant validation command and report whether it passed.

## 1. Global Core Rules

### 1-1. Determinism
- Follow rules exactly.
- Use deterministic naming, paths, and architecture.
- Do not invent new patterns unless explicitly requested.
- Prefer explicitness over clever abstractions.

### 1-2. Request Uncertainty Policy
- Before implementation, run the intake gate skill.
- Ask before implementation when correctness depends on unclear:
  - API/request/response contract
  - DB schema/migration/constraint/index
  - Auth/permission/role
  - Business rules (billing/coupon/scheduling/etc.)
  - Cross-feature dependency direction
- Hard-Block questions must be asked as a numbered list so users can answer by number.
- Minor copy/spacing/icon/empty/loading UX may use reversible defaults.

### 1-3. Output and Naming
- All code must be syntactically valid.
- All file paths must use forward slashes.
- All imports must resolve to real files.
- In `apps/web/src`, JSX files use `.jsx`; non-JSX modules use `.js`.
- Components: PascalCase
- Hooks/utils/stores: camelCase (unless explicitly defined otherwise)

### 1-4. Comment Language
- Comments/docstrings must be Korean.
- Proper nouns remain in original form.
- When editing a file, convert touched English comments/docstrings in that file to Korean unless external specs require English.

## 2. Scoped Architecture
- Frontend-specific rules live in `apps/web/AGENTS.md`.
- Backend-specific rules live in `apps/api/AGENTS.md`.
- When editing scoped paths, obey the nearest nested `AGENTS.md` in addition to this root file.
- Keep root instructions small; move workflow details to skills and path-specific architecture rules to scoped `AGENTS.md`.

## 3. Environment Core
- Assume offsite/local development may not have corporate network access.
- Never hardcode intranet URLs.
- External dependency URLs must remain env-driven.
- Exception: approved internal package or driver artifact URLs may be pinned in OIDC/prod-only Compose build args when the artifact is versioned, not a credential or user-specific endpoint, unused by `docker-compose.dev.yml`, and documented in `docs/configuration.md`.
- If auth/RAG/assistant/mail contract changes, local mock/dev wiring must stay runnable.
- Backend tests/commands must run in Docker Compose `api` container.
- Detailed offsite sync steps are in `offsite-dev-contract-sync` skill.

### 3-1. File Data Mount Convention
- New or changed API-readable business file data must mount under `/data/<domain>` inside the `api` container; use lowercase snake_case domain names.
- Compose host paths must be env-driven as `${<DOMAIN>_DATA_HOST_PATH:-../data/<domain>}` unless an existing shared host path is being reused.
- Django settings must expose the container path as `<DOMAIN>_DATA_ROOT`; file-level settings may use `<DOMAIN>_<NAME>_PATH` only when the source contract requires individual files.
- Source/reference datasets must be mounted read-only with `:ro`; use read-write mounts only for app-owned uploads, generated files, or processing queues.
- When an API file mount is added or changed, keep `compose/dev.app.yml`, `compose/oidc.app.yml`, `compose/prod.app.yml`, `env/api.common.env`, and `docs/configuration.md` in sync.
- Do not introduce new `/appdata` container paths. Existing `/appdata` paths should move to `/data/<domain>` when their mount contract is touched.

## 4. Output Scope Control
- Keep modifications strictly within requested scope.
- Preserve public surfaces unless explicitly requested.
- Avoid unrelated refactors.
- Do not output full file contents in responses; provide concise diffs or minimal relevant snippets only. Full-file output requires an explicit user request.
- For detailed output format/path completeness rules, use `safe-file-edit-output` skill.

## 5. Git Workflow
- Do not automatically commit or push after file changes.
- Commit only when the user explicitly requests a commit, push, PR, or release-ready Git finalization.
- When committing, stage only changes made for the current requested task. Never stage unrelated user changes.
- Before committing, run the relevant validation for the changed area when one exists. If validation cannot run, report why.
- Push only when the user explicitly requests push or PR creation, or when the requested Git finalization clearly requires pushing.
- If commit or push is blocked by validation failure, merge conflict, authentication, missing remote, or branch policy, stop and report the reason.

### 5-1. Commit Message Rule
- Commit messages must start with an app/area scope prefix.
- Use the format `[scope] type: summary`.
- Example: `[appstore] fix: 앱 등록 상태 표시 오류 수정`
- When a change spans multiple apps/areas, combine prefixes in dependency order.
- Example: `[api][web] feat: 앱 권한 동기화 추가`
- Allowed `type` values: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`.
- Keep `summary` short and describe the purpose of the change.

### 5-2. Commit Scopes
- `[web]`: `apps/web`
- `[api]`: `apps/api`
- `[appstore]`: appstore domain changes
- `[account]`: account domain changes
- `[assistant]`: assistant or RAG domain changes
- `[emails]`: emails domain changes
- `[drone]`: drone, inform, SOP, messenger, or Jira notification domain changes
- `[observer]`: observer domain changes
- `[line-dashboard]`: line dashboard domain changes
- `[data-movement]`: data movement or Airflow data pipeline changes
- `[pm-comparison]`: PM comparison domain changes
- `[l3-spider]`: L3 spider domain changes
- `[fdc-trend]`: FDC trend domain changes
- `[voc]`: VOC domain changes
- `[auth]`: auth domain changes
- `[access-stats]`: access stats domain changes
- `[home]`: home shell or portal entry changes
- `[teamstaff]`: teamstaff domain changes
- `[infra]`: compose, env, Docker, deploy, CI, or operational scripts
- `[docs]`: documentation-only changes
- `[agent]`: `AGENTS.md`, `.codex/skills`, or agent support scripts
- `[repo]`: repository-wide shared configuration that does not fit a narrower scope
