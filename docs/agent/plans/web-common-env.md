# ExecPlan: web common env

## 목표
- 여러 web env 파일에 중복된 TTTM Spider URL env를 공통 env 파일로 분리한다.
- dev, OIDC dev, prod web 서비스가 같은 공통 값을 사용하도록 Compose wiring을 정리한다.

## 현재 상태
- TTTM Spider URL env가 `env/web.dev.env`, `env/web.oidc.dev.env`, `env/web.prod.env`에 중복되어 있다.
- `compose/prod.app.yml`은 Vite build arg로 TTTM Spider URL env를 별도 전달한다.
- TTTM Spider 기능 코드와 observer CSS에 기존 미커밋 변경이 있으며 이번 작업에서 건드리지 않는다.

## 범위
- 추가: `env/web.common.env`
- 수정: `env/web.dev.env`, `env/web.oidc.dev.env`, `env/web.prod.env`
- 수정: `compose/dev.app.yml`, `compose/oidc.app.yml`, `compose/prod.app.yml`
- 수정: `docs/configuration.md`
- 제외: TTTM Spider React 코드, Dockerfile, observer CSS

## 설계
- 공통 브라우저 노출 URL은 `env/web.common.env`에 둔다.
- 각 web 서비스의 `env_file`은 공통 파일을 먼저 읽고 환경별 파일을 나중에 읽는다.
- 운영 Vite 정적 빌드는 build arg가 필요하므로 `compose/prod.app.yml`의 TTTM Spider URL build arg는 유지한다.
- 2026-07-07 이후 TTTM Spider URL은 코드 상수로 전환되어 이 env/build arg 계약은 제거되었다.

## 실행 단계
- [x] `env/web.common.env`를 생성한다.
- [x] 환경별 web env 파일에서 TTTM Spider URL env 중복 값을 제거한다.
- [x] dev/OIDC/prod web 서비스에 공통 env 파일을 추가한다.
- [x] 문서를 갱신한다.
- [x] Compose 설정을 검증한다.

## 검증
- `docker compose -f docker-compose.dev.yml config`
- `docker compose -f docker-compose.oidc.yml config`
- `docker compose config`
- `rg -n "TTTM Spider" env compose apps/web/Dockerfile apps/web/README.md docs/configuration.md`

## 위험과 대응
- 위험: prod build arg는 service `env_file`을 직접 참조하지 못해 공통 env만으로 빌드 시점 값이 자동 전달되지 않을 수 있다.
- 대응: `compose/prod.app.yml`의 build arg fallback을 유지하고 문서에 운영 override 방법을 명시한다.

## 진행 기록
- 2026-07-07: TTTM Spider URL을 web common env로 분리하기로 결정했다.
- 2026-07-07: `env/web.common.env`를 추가하고 환경별 web env 파일의 중복 선언을 제거했다.
- 2026-07-07: dev/OIDC/prod web 서비스가 `env/web.common.env`를 먼저 읽도록 연결했다.
- 2026-07-07: `docs/configuration.md`에 web common env와 Vite build-time 주의사항을 추가했다.
- 2026-07-07: dev/OIDC/prod Compose config가 모두 통과했고 각 web 서비스에 TTTM Spider URL이 주입됨을 확인했다.
- 2026-07-07: TTTM Spider URL env 계약은 코드 상수 하드코딩으로 대체되어 제거되었다.
