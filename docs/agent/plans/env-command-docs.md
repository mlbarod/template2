# ExecPlan: 환경 실행 문서 정리

## 목표
- `make`를 일반 사용자의 실행 진입점으로 명확히 문서화한다.
- `dev`는 로컬 전용 public source, `oidc`와 `prod`는 내부 mirror source를 사용한다는 정책을 한눈에 보이게 정리한다.
- `app`과 `infra`의 포함 서비스와 실행 명령을 README, 사용방법, 운영 문서, 환경 설정 문서에서 일관되게 설명한다.

## 현재 상태
- `README.md`, `사용방법.md`, `docs/operations.md`가 `make` 사용을 설명하지만 dev/public과 oidc/prod/internal mirror 정책이 분산되어 있다.
- `docs/configuration.md`에는 내부 mirror 적용 형식이 있으나 환경별 정책 표가 없다.
- `Makefile`의 infra 목록에 실제 compose 서비스가 아닌 `airflow-code`가 남아 있다.
- `docs/integrations/proxy-mirrors.md`는 mirror catalog와 베이스 주소 패턴을 담고 있다.

## 범위
- 수정할 영역: `Makefile`, `README.md`, `사용방법.md`, `docs/operations.md`, `docs/configuration.md`, `docs/inventory.md`, 필요 시 mirror catalog 안내 문구.
- 수정하지 않을 영역: compose 서비스 구조, Dockerfile build arg 동작, 앱 env contract, DB/API/auth 설정.

## 설계
- 사용자 실행 표기는 `make dev`, `make oidc`, `make prod` 중심으로 유지한다.
- compose 파일 직접 실행은 디버깅/검증용 구현 세부사항으로 낮춰 설명한다.
- 환경 정책은 `dev = local + public`, `oidc/prod = internal + mirror`로 표현한다.
- `app`은 API/Web/Nginx/MinIO 계열, dev에서는 dummy ADFS 포함으로 설명한다.
- `infra`는 Airflow DB/Webserver/Scheduler/Init/FTP로 설명하고, prod에는 monitoring이 compose에 포함됨을 별도 설명한다.

## 실행 단계
- [x] Makefile infra 서비스 목록을 실제 compose 서비스와 맞춘다.
- [x] README의 실행 섹션을 환경/명령 중심으로 정리한다.
- [x] `사용방법.md`를 사용자 관점의 상세 실행 가이드로 재정리한다.
- [x] `docs/operations.md`의 실행/검증 섹션을 같은 용어로 맞춘다.
- [x] `docs/configuration.md`에 환경별 dependency source 정책 표를 추가한다.
- [x] 문서 감사에서 잡힌 inventory/operations drift를 맞춘다.
- [x] 문서/compose 검증을 실행한다.

## 검증
- 통과: `make -n dev-infra-up`
- 통과: `make -n oidc-infra-up`
- 통과: `make -n prod-infra-up`
- 통과: `make -n dev-infra-build && make -n oidc-infra-build && make -n prod-infra-build`
- 통과: `docker compose -f docker-compose.dev.yml build airflow-init airflow-webserver airflow-scheduler`
- 통과: `bash scripts/agent/check_compose_configs.sh`
- 통과: `npm run agent:audit:docs`
- 통과: `git diff --check -- Makefile README.md 사용방법.md docs/operations.md docs/configuration.md docs/integrations/proxy-mirrors.md docs/inventory.md docs/agent/plans/env-command-docs.md`
- 확인: `docker compose -f docker-compose.dev.yml config | rg "repository\\.samsungds\\.net|repo\\.samsungds\\.net"` 결과 없음
- 확인: `docker compose -f docker-compose.oidc.yml config | rg "repository\\.samsungds\\.net|repo\\.samsungds\\.net"`
- 확인: `docker compose -f docker-compose.yml config | rg "repository\\.samsungds\\.net|repo\\.samsungds\\.net"`

## 위험과 대응
- 위험: 문서가 compose 내부 구조까지 과도하게 설명해 다시 복잡해질 수 있다.
- 대응: README는 빠른 사용법, 사용방법은 상세 명령, configuration은 정책, proxy mirror 문서는 catalog로 역할을 나눈다.
- 위험: Makefile 서비스 목록과 compose 서비스가 다르면 문서화한 명령이 실패한다.
- 대응: compose config service 목록과 Makefile dry-run을 함께 확인한다.

## 진행 기록
- 2026-07-08: dev는 로컬/public 전용, oidc/prod는 내부 mirror 전용이라는 기준으로 문서 정리 계획을 작성했다.
- 2026-07-08: README, 사용방법, operations, configuration을 `make`/환경/source/app-infra 기준으로 재정리했다.
- 2026-07-08: Makefile의 존재하지 않는 `airflow-code` infra 참조를 제거했다.
- 2026-07-08: 문서 감사에서 누락으로 잡힌 activity endpoint/model과 `summarize_ct_process_comment` command 색인을 보강했다.
