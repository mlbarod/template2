# ExecPlan: monitoring stack

## 목표
- 운영 Compose 스택에 Grafana 기반 모니터링을 추가한다.
- 서버와 컨테이너의 CPU, 메모리, 디스크, 네트워크 부하와 추세를 확인할 수 있게 한다.

## 현재 상태
- 운영 진입점은 `docker-compose.yml`이며 `compose/prod.infra.yml`, `compose/prod.app.yml`을 include한다.
- 모니터링 스택은 앱이 아닌 운영 인프라로 보고 `compose/prod.infra.yml`에서 include한다.
- 앱은 `shared-net` 외부 Docker network를 사용한다.
- API는 gunicorn으로 실행되고 있지만 Django 내부 endpoint latency metric은 아직 노출하지 않는다.
- 기존 미커밋 변경은 `apps/web/src/features/observer/components/observer.css`이며 이번 작업에서 건드리지 않는다.

## 범위
- 추가: `compose/monitoring.yml`
- 추가: Prometheus 설정, Grafana datasource/dashboard provisioning
- 추가: Grafana env 템플릿
- 수정: `docker-compose.yml`, `docs/configuration.md`
- 제외: Django instrumentation, nginx stub status, Kubernetes manifest

## 설계
- Prometheus가 `prometheus`, `node-exporter`, `cadvisor` target을 scrape한다.
- node-exporter는 host CPU/메모리/디스크/네트워크 지표를 제공한다.
- cAdvisor는 Docker container별 CPU/메모리/네트워크/파일시스템 지표를 제공한다.
- Grafana는 Prometheus datasource와 기본 dashboard를 provisioning으로 자동 등록한다.
- Grafana admin 계정, bind address, 포트는 env로 제어한다. 기본 bind address는 외부 접속을 위해 `0.0.0.0`으로 둔다.

## 실행 단계
- [x] monitoring compose 파일을 추가한다.
- [x] Prometheus scrape 설정을 추가한다.
- [x] Grafana datasource/dashboard provider와 dashboard JSON을 추가한다.
- [x] `docker-compose.yml` include와 `docs/configuration.md`를 갱신한다.
- [x] `docker compose config`로 문법을 검증한다.

## 검증
- `docker compose config`
- `git status --short --branch`

## 위험과 대응
- 위험: Grafana가 외부 접속 가능 상태로 노출된다.
- 대응: 비밀번호는 사용자 지정값으로 설정하고, 필요 시 방화벽 또는 `GRAFANA_BIND_ADDRESS=127.0.0.1`로 제한한다.
- 위험: Prometheus/cAdvisor가 Docker socket 또는 host fs를 읽어 보안 민감도가 올라간다.
- 대응: Prometheus는 외부 포트를 열지 않고 Grafana만 노출한다.

## 진행 기록
- 2026-07-07: Compose 기반 모니터링 스택을 추가하기로 결정했다.
- 2026-07-07: Grafana, Prometheus, node-exporter, cAdvisor compose와 provisioning 파일을 추가했다.
- 2026-07-07: `docker compose config`, Prometheus config check, Grafana dashboard JSON parse 검증을 통과했다.
- 2026-07-07: Grafana 기본 bind address를 외부 접속용 `0.0.0.0`으로 변경하고 admin password를 사용자 지정값으로 설정했다.
- 2026-07-07: 모니터링 include 위치를 `docker-compose.yml`에서 `compose/prod.infra.yml`로 이동했다.
