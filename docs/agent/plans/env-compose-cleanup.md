# ExecPlan: env compose cleanup

## 목표
- 환경 변수와 Compose 파일을 더 관리하기 쉽게 정리한다.
- 앱 동작과 배포 진입점은 유지하면서 중복과 검증 누락을 줄인다.

## 현재 상태
- `env/`는 API/Web/infra 파일로 나뉘어 있으나 일부 build-time/runtime 기준이 문서에만 부분적으로 정리되어 있다.
- `compose/airflow.yml`은 여러 Airflow 서비스가 동일한 environment 블록을 반복한다.
- dev/OIDC/prod Compose 진입점은 각각 `docker-compose.dev.yml`, `docker-compose.oidc.yml`, `docker-compose.yml`이다.
- 작업트리에 TTTM Spider, monitoring, observer CSS 관련 기존 미커밋 변경이 있어, 이번 작업은 env/compose/docs/scripts 범위로 제한한다.

## 범위
- 수정: `compose/airflow.yml`
- 수정: `docs/configuration.md`
- 추가: Compose/env 검증 스크립트
- 제외: API/Web 기능 코드, secret 값 제거, 서비스 endpoint 변경, 실제 배포 실행

## 설계
- Airflow 공통 environment는 YAML anchor로 한 곳에서 관리한다.
- 서비스별 추가 env만 개별 environment에 남긴다.
- Airflow 공통 environment에는 runtime과 DAG 공통 연결/인증 값만 둔다.
- DAG별 schedule/timeout/limit/dry-run 기본값은 각 DAG 코드에 둔다.
- Compose 검증은 하나의 스크립트로 dev/OIDC/prod 진입점을 모두 확인한다.
- secret 제거는 현재 배포 계약 변경 위험이 있어 이번 범위에서는 문서상 관리 원칙만 명시한다.

## 실행 단계
- [x] Airflow 공통 environment anchor를 추가한다.
- [x] 반복 environment 블록을 anchor merge로 교체한다.
- [x] Compose/env 검증 스크립트를 추가한다.
- [x] configuration 문서에 env/Compose 관리 원칙과 검증 방법을 추가한다.
- [x] dev/OIDC/prod Compose config를 검증한다.

## 검증
- `bash scripts/agent/check_compose_configs.sh`
- `docker compose config`
- `docker compose -f docker-compose.dev.yml config`
- `docker compose -f docker-compose.oidc.yml config`

## 위험과 대응
- 위험: YAML anchor merge가 Compose config 결과를 바꿀 수 있다.
- 대응: 변경 후 세 Compose 진입점 config를 모두 실행한다.
- 위험: secret 값을 옮기면 배포가 깨질 수 있다.
- 대응: 이번 변경에서는 secret 값 위치를 바꾸지 않고 문서로만 분류 기준을 명시한다.

## 진행 기록
- 2026-07-07: env/Compose 구조 정리를 시작했다.
- 2026-07-07: Airflow 공통 environment를 YAML anchor로 정리하고 Compose config 검증 스크립트를 추가했다.
- 2026-07-07: `docs/configuration.md`에 env/Compose 관리 원칙과 검증 명령을 추가했다.
- 2026-07-07: `bash scripts/agent/check_compose_configs.sh`와 `git diff --check`가 통과했다.
- 2026-07-07: Airflow 공통 env에서 DAG별 schedule/timeout/limit/dry-run 기본값을 제거하고 DAG 코드 기본값을 기준으로 삼았다.
