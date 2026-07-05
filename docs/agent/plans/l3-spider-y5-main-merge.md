# ExecPlan: L3 Spider y5 Main Merge

## 목표
- `y5` 브랜치의 L3 Spider 개편 내용을 `main`에 병합한다.
- 충돌은 `y5`의 요약 화면/트렌드/집계 개편 로직을 최대한 우선하여 해결한다.
- L3 Spider 외 Drone, Line Dashboard 등 현재 미커밋 작업은 건드리지 않는다.

## 현재 상태
- 현재 브랜치는 `main`이고 `y5`는 `origin/y5` 최신 커밋 `3fbce5fe`를 추적한다.
- `main`과 `y5` 병합 시 L3 Spider 내부 2개 파일에서 충돌이 예상된다.
- 작업트리에는 Drone, Line Dashboard, `env/api.prod.env` 관련 미커밋 변경이 존재한다.

## 범위
- 수정할 영역: `apps/api/api/l3_spider`, `apps/web/src/features/l3-spider`, L3 Spider 관련 문서/예시/목 데이터 스크립트.
- 수정하지 않을 영역: Drone, Line Dashboard, 환경 파일의 기존 미커밋 변경.

## 설계
- API contract: `y5`의 `/api/v1/l3_spider/trend` 추가를 수용한다.
- DB schema: Django migration 변경은 없다. SQLite file index의 optional column/read fallback을 사용한다.
- Auth/env: 새 인증, 권한, env contract는 추가하지 않는다.
- 충돌 해결: 충돌 파일은 `y5` 버전을 기준으로 두고, 컴파일 또는 런타임에 필요한 `main` 쪽 L3 Spider 보정만 최소 병합한다.

## 실행 단계
- [x] 병합 전 작업트리와 병합 대상 겹침 확인
- [x] `y5`를 `main`에 병합
- [x] L3 Spider 충돌 파일을 `y5` 우선으로 해결
- [x] import/export/API 연결 정합성 확인
- [x] 가능한 검증 명령 실행

## 검증
- `npm run web:build`: 통과
- `npm run agent:audit:web-boundary`: 통과
- `npm run agent:audit:ui`: 통과
- `npm run agent:audit:api-boundary`: 통과
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py test api.l3_spider --keepdb`: 통과
- `npm run agent:audit:docs`: 실패. 기존 `docs/inventory.md`의 activity endpoint/model 누락(`app-access-sync-external`, `ExternalAppUsageSyncState`)으로, 이번 L3 Spider 병합 범위 밖이다.

## 위험과 대응
- 위험: `main`에만 있던 L3 Spider 보정 로직이 `y5` 우선 병합 중 누락될 수 있다.
- 대응: 충돌 파일은 `y5`를 기본으로 하되, API/view/service 연결과 집계 fallback을 검토한다.
- 위험: 현재 작업트리의 unrelated 변경이 병합 결과와 섞여 보일 수 있다.
- 대응: 상태 확인 시 병합 파일과 기존 dirty 파일을 분리해 보고한다.

## 진행 기록
- 2026-07-06: `y5` 우선 병합 요청에 따라 병합 계획을 작성했다.
- 2026-07-06: L3 Spider 충돌 2건을 `y5` 우선으로 해결하고, 실제 파일 구조에 맞춘 `line_name_rules` import, `/trend` 인증, 테스트 계약을 보정했다.
