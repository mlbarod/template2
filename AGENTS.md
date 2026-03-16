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
- Korean-commented Python output: `.codex/skills/write-commented-python/SKILL.md`
- Frontend layout composition: `.codex/skills/compose-frontend-layout/SKILL.md`
- Safe file edit/output format: `.codex/skills/safe-file-edit-output/SKILL.md`
- Offsite contract synchronization: `.codex/skills/offsite-dev-contract-sync/SKILL.md`

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

## 2. Frontend Core Architecture

### 2-1. Feature Boundary
- Feature path: `apps/web/src/features/<feature>`
- Allowed subpaths only:
  - `pages/`
  - `components/`
  - `hooks/`
  - `api/`
  - `store/`
  - `utils/`
  - `routes.jsx`
  - `index.js`
- Folder depth rule:
  - Default: max depth 2
  - One extra level under `components/` only when:
    - the feature already has 12+ component files, or grouping is explicitly requested
    - subfolder name is one of: `list`, `detail`, `form`, `dialog`, `table`, `chart`, `filters`, `cards`, `sections`
    - no further nesting
  - If another subfolder name is needed, ask first.

### 2-2. Public Facade
- `apps/web/src/features/<feature>/index.js` is the only public surface.
- Named exports only.
- `export *` is forbidden.
- Cross-feature imports must use:
  - `import { something } from "@/features/<otherFeature>"`
- Explicit `@/features/<otherFeature>/index.js` import is forbidden.
- Direct imports to another feature's internals are forbidden (`components/*`, `pages/*`, `api/*`, etc.).

### 2-3. Import Rules
- Prefer `@/` for project-internal absolute imports.
- `components/*` alias is allowed only for `components/...` paths.
- Do not mix `@/components/...` and `components/...` in one file.
- Keep existing alias style when editing.
- Project-internal absolute imports must resolve under:
  - `apps/web/src/components/ui/*`
  - `apps/web/src/components/layout/*`
  - `apps/web/src/components/common/*`
  - `apps/web/src/lib/*`
  - `apps/web/src/features/<otherFeature>` (facade only)

### 2-4. UI/Route/Data Rules
- Do not manually edit `apps/web/src/components/ui/**` unless explicitly requested via shadcn CLI flow.
- Every feature must expose `routes.jsx`.
- Global routes only in `apps/web/src/routes/*`.
- Routes may compose `components/layout/*`, but must not define layout components in `routes/*`.
- Routes must not contain business logic/data logic/derived UI logic.
- React Query is the single source of truth for server data.
- Use array query keys, avoid redundant keys, and invalidate minimum scope.
- Never mirror server data to Zustand.
- Zustand is only for feature-local UI/interaction flow state.

### 2-5. Styling/React/Layout Core
- Tailwind only; use design tokens; use `dark:` for dark mode.
- Arbitrary HEX and inline style are forbidden unless strictly necessary.
- Avoid premature optimization (`useMemo`, `useCallback`, `React.memo` only when required).
- Layout core constraints:
  - one scroll container per axis per region
  - scrollable elements require `min-h-0`
  - page skeleton: `h-screen flex flex-col` + fixed header + `flex-1 min-h-0 overflow-hidden`
- Detailed layout recipes are in `compose-frontend-layout` skill.

## 3. Backend Core Architecture

### 3-1. Domain App Boundary
- Domain app path: `apps/api/api/<feature>` (`api.<feature>`)
- Allowed files/folders only:
  - `apps.py`, `models.py`, `urls.py`, `callback_urls.py` (auth only)
  - `views.py`, `serializers.py`, `selectors.py`, `permissions.py`, `admin.py`, `tests.py`
  - `services/`, `migrations/`, `management/commands/`
- No new backend folders outside approved paths.
- Max depth 2, except `services/`, `migrations/`, `management/commands/`.
- Shared/infrastructure packages only:
  - `apps/api/api/common`
  - `apps/api/api/auth`
  - `apps/api/api/rag`
  - `apps/api/api/management`

### 3-2. Cross-Feature and Responsibilities
- Cross-feature imports allowed only through other feature's `services/__init__.py` facade or `selectors.py`.
- `views.py`: HTTP only
- `serializers.py`: schema + validation only
- `permissions.py`: DRF permissions only
- `services/*`: business logic, writes, transactions, external calls
- `selectors.py`: read-only ORM queries only
- `models.py`: schema + pure domain rules only
- Views/services must not execute direct read ORM queries; use selectors.

### 3-3. Routing and API Shape
- Use versioned API prefix `/api/v1/<route-scope>/...`
- Exception: auth callbacks under `/auth/` (`api.auth.callback_urls`)
- Global routing only in `apps/api/api/urls.py` as include registry.
- Feature `urls.py` must define relative paths only.
- Routes contain no business logic.

### 3-4. Model/DB Core Rules
- Fields: snake_case
- Models: singular PascalCase
- Every model sets `db_table = "<feature>_<entity>"`
- Primary key: `id` (BigAutoField), UUID only when externally required
- Timestamps timezone-aware UTC (`created_at` required; `updated_at`, `deleted_at` optional)
- Index/constraint naming:
  - `idx_<table>_<cols>`
  - `uniq_<table>_<cols>`
  - max length <= 30
  - apply deterministic abbreviation/suffix rule
- Full naming map/playbook is maintained in `create-django-feature` skill.

### 3-5. Safety and Readability
- Wrap multi-step writes in `transaction.atomic()`.
- No writes in selectors/models.
- Prefer explicit, linear, small single-purpose code.
- Keep functions/classes small and single-purpose where practical (about 30–50 lines).
- Add type hints and Korean docstrings to public services/selectors.

### 3-6. Testing and Migrations
- Update/add tests when business logic changes.
- Prefer service/selector tests; keep view tests minimal.
- Never edit applied migrations.
- Tests must not directly import other domain internal modules.
- Domain-specific commands stay in each feature app.
- Shared commands use service/selector facade only.
- Detailed execution sequence and commands are in `django-test-migration-flow` skill.

## 4. Environment Core
- Assume offsite/local development may not have corporate network access.
- Never hardcode intranet URLs.
- External dependency URLs must remain env-driven.
- If auth/RAG/assistant/mail contract changes, local mock/dev wiring must stay runnable.
- Backend tests/commands must run in Docker Compose `api` container.
- Detailed offsite sync steps are in `offsite-dev-contract-sync` skill.

## 5. Output Scope Control
- Keep modifications strictly within requested scope.
- Preserve public surfaces unless explicitly requested.
- Avoid unrelated refactors.
- Do not output full file contents in responses; provide concise diffs or minimal relevant snippets only. Full-file output requires an explicit user request.
- For detailed output format/path completeness rules, use `safe-file-edit-output` skill.
