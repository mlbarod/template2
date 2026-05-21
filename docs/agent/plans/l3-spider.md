# ExecPlan: L3 Spider 이식

## 목표
- 외부 원본이었던 `b-main`의 반도체 이상감지 대시보드를 현재 모노레포의 Django/React feature로 이식한다.
- frontend/backend feature 간 독립성을 유지하고 로그인 사용자만 접근하게 한다.

## 현재 상태
- 외부 앱은 `b-main`에 React/Vite/TypeScript/FastAPI 단독 앱으로 존재했으며, 이식 후 원본 폴더는 제거한다.
- 현재 프로젝트 frontend feature는 `apps/web/src/features/<feature>` 경계와 facade를 사용한다.
- 현재 프로젝트 backend domain app은 `apps/api/api/<feature>` 경계와 versioned API prefix를 사용한다.

## 범위
- 추가: `apps/api/api/l3_spider`, `apps/web/src/features/l3-spider`.
- 수정: Django settings/url registry, compose/env 데이터 mount 계약, web router/nav, web dependency.
- 제외: 기존 feature refactor, 실제 원격 서버 mount 구성 자동화.

## 설계
- API prefix는 `/api/v1/l3_spider/`를 사용한다.
- backend는 `L3_SPIDER_DATA_ROOT` 경로의 Parquet 파일을 read-only로 조회한다.
- 요청/응답 JSON은 camelCase를 사용하고, backend 내부 파일/컬럼 접근은 원본 Parquet 컬럼명과 분리한다.
- frontend는 `apps/web/src/features/l3-spider/index.js` facade를 통해 route만 노출한다.
- server data는 React Query로 조회하고, 선택/체크박스/차트 모드는 feature-local UI state로만 유지한다.
- DB schema를 만들지 않으므로 migration은 필요하지 않다.

## 실행 단계
- [x] ExecPlan 작성
- [x] Django `api.l3_spider` feature 생성
- [x] Parquet meta/summary/data API 구현
- [x] React `l3-spider` feature 생성
- [x] 라우터, 내비게이션, env, dependency 연결
- [x] backend/frontend 검증 실행

## 검증
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py check`
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py test api.l3_spider`
- `npm run web:lint`
- `npm run web:build`
- `npm run agent:audit:web-boundary`
- `npm run agent:audit:ui`

## 위험과 대응
- 위험: 원격 서버 데이터를 직접 읽으면 장애와 지연이 API 요청에 전파된다.
- 대응: 원격 데이터는 호스트/컨테이너에 read-only mount하고 앱은 로컬 파일 경로처럼 읽는다.
- 위험: Parquet 파일 수가 많으면 `/meta`와 `/summary`가 느려질 수 있다.
- 대응: column projection과 panel sampling을 유지하고, 필요 시 후속 작업에서 파일 index/cache를 추가한다.

## 진행 기록
- 2026-05-21: route `/l3_spider`, 로그인 사용자 접근, env 기반 read-only mount, camelCase API 계약으로 확정했다.
- 2026-05-21: Django API, React feature, Docker volume/env, frontend route/nav, Plotly dependency 연결을 구현했다.
- 2026-05-21: Django check/test, migration dry-run, web lint/build, 전체 agent audit를 실행했다.
