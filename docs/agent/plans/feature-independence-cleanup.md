# ExecPlan: Feature Independence Cleanup

## 목표
- feature별 담당자가 자기 feature 내부에서 다른 feature 구현에 의존하지 않고 개발할 수 있게 한다.
- frontend feature 내부 cross-feature import를 제거하고, 필요한 공유 계약은 `lib` 또는 `components/layout`으로 이동한다.
- backend에서 `account`가 `drone` domain side effect를 직접 호출하지 않게 한다.

## 현재 상태
- frontend boundary audit는 기존 기준으로 통과하지만, feature facade 경유 cross-feature import는 허용하고 있다.
- `ChatWidget`이 여러 feature shell에서 직접 import된다.
- home layout alias exports가 `features/home`에서 layout 역할로 공개된다.
- `account` feature facade가 계정 UI와 공통 사용자/소속 API를 함께 공개한다.
- backend `api.account.apps.AccountConfig.ready()`가 `api.drone.services`를 호출한다.

## 범위
- 수정할 영역:
  - `apps/web/src/features/*`
  - `apps/web/src/components/layout/*`
  - `apps/web/src/lib/*`
  - `scripts/agent/check_frontend_boundaries.sh`
  - `apps/api/api/account/apps.py`
  - `apps/api/api/drone/apps.py`
- 수정하지 않을 영역:
  - API URL/response contract
  - DB schema/migrations
  - 화면 디자인 대규모 변경
  - unrelated oversized file decomposition

## 설계
- feature 내부에서는 다른 feature facade도 import하지 않는다.
- global route/layout 조립 계층만 feature routes를 import한다.
- assistant widget은 shared layout shell에서 렌더링한다.
- account의 공통 사용자/소속 조회 API는 `lib/account`로 노출한다.
- backend 사용자 변경에 따른 drone 후처리는 `drone` 앱이 signal receiver를 등록한다.
- migration/env/auth contract 변경은 없다.

## 실행 단계
- [x] 관련 frontend imports와 layout/account 코드 조사
- [x] home layout alias exports를 layout 계층으로 이동
- [x] `ChatWidget` 렌더링을 layout 계층으로 이동하고 feature shell imports 제거
- [x] account 공통 API/hook/card를 shared 계층으로 이동 또는 래핑
- [x] assistant-emails 직접 의존 제거
- [x] frontend boundary audit를 feature 내부 cross-feature facade import 금지로 강화
- [x] backend account-drone signal 등록 위치 변경
- [x] feature import 정책 문서와 `apps/web/AGENTS.md` 정합화
- [x] PR/CI/AI 작업 가이드로 feature 독립성 유지 장치 추가
- [x] frontend/backend 검증 실행

## 검증
- `scripts/agent/check_frontend_boundaries.sh`
- `npm --prefix apps/web run lint`
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py test api.account api.drone`

## 위험과 대응
- 위험: ChatWidget 위치 변경으로 일부 route에서 widget 중복/누락 가능
- 대응: root/layout shell에서 단일 렌더링하고 feature shell의 중복 렌더링을 제거한다.
- 위험: account 공통 계약 이동 중 import surface가 깨질 수 있음
- 대응: 기존 account facade export는 호환 유지하되 cross-feature 사용처는 `lib`로 변경한다.
- 위험: backend signal 이동으로 receiver 미등록 가능
- 대응: `api.drone`이 INSTALLED_APPS에 있으므로 `DroneConfig.ready()`에서 receiver 등록한다.

## 진행 기록
- 2026-06-12: feature 독립성 확보를 위한 범위와 검증 방법을 정의했다.
- 2026-06-12: `lib/account`와 portal layout 계층을 추가하고 feature 내부 cross-feature import를 제거했다.
- 2026-06-12: `account`의 drone 후처리 호출을 제거하고 `drone` 앱의 user post_save receiver로 이동했다.
- 2026-06-12: `scripts/agent/check_frontend_boundaries.sh`, `npm --prefix apps/web run lint`, `python3 -m py_compile apps/api/api/account/apps.py apps/api/api/drone/apps.py` 통과.
- 2026-06-12: `docker compose -f docker-compose.dev.yml exec -T api python manage.py test api.account api.drone`는 `api` 서비스 미실행으로 실패했고, `up -d api` 후에도 dev DB `dashboard` 부재로 컨테이너가 종료되어 실행하지 못했다.
- 2026-06-12: feature 내부 cross-feature import 금지 정책을 `apps/web/AGENTS.md`, `docs/architecture.md`, `docs/frontend.md`에 반영했다.
- 2026-06-12: 문서 정합화 후 boundary audit, frontend lint, Python compile을 재실행해 통과했다. Django Docker 테스트는 `dashboard` DB 부재로 `api` 컨테이너가 종료되어 재실행하지 못했다.
- 2026-06-12: 코드리뷰 지적사항을 반영해 account hook export 누락을 복구하고, assistant mailbox 접근 필터를 route 계층 prop/context 전달로 복원했다.
- 2026-06-12: frontend boundary audit가 multi-line feature facade import도 탐지하도록 보강하고, Portal 외부 링크를 `VITE_PORTAL_*` env 기반으로 변경했다.
- 2026-06-12: `scripts/agent/check_frontend_boundaries.sh`, `npm --prefix apps/web run lint`, `npm --prefix apps/web run build`, `python3 -m py_compile apps/api/api/account/apps.py apps/api/api/drone/apps.py` 통과.
- 2026-06-12: 운영 Docker build args에 `VITE_PORTAL_*` 전달을 추가하고, assistant mailbox query가 인증 사용자 확인 후 실행되도록 `enabled` 옵션을 연결했다.
- 2026-06-12: 최종 확인으로 boundary audit, frontend lint/build, backend py_compile, `git diff --check` 통과.
- 2026-06-12: `.github/workflows/feature-guardrails.yml`, `.github/pull_request_template.md`, `docs/agent/ai-feature-workflow.md`를 추가해 다른 브랜치와 AI 작업에서도 같은 구조 규칙을 따르도록 했다.
- 2026-06-12: guardrail 추가 후 `npm run agent:audit:web-boundary`, `npm run web:lint`, `npm run web:build`, `python3 -m compileall -q apps/api`, `git diff --check` 통과.
