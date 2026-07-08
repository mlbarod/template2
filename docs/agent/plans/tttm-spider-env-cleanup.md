# ExecPlan: TTTM Spider env cleanup

## 목표
- TTTM Spider iframe URL을 코드 상수로 고정한 뒤 더 이상 사용하지 않는 TTTM Spider URL env 계약을 제거한다.

## 현재 상태
- `apps/web/src/features/tttm-spider/pages/TttmSpiderPage.jsx`는 `http://10.172.60.187:32710`을 직접 iframe `src`로 사용한다.
- `env/web.common.env`, `compose/prod.app.yml`, `apps/web/Dockerfile`, `apps/web/README.md`, `docs/configuration.md`에 기존 env 계약이 남아 있다.

## 범위
- 수정: web env 파일, prod compose build arg, web Dockerfile, web/configuration 문서
- 제외: 과거 의사결정 기록인 기존 `docs/agent/plans/*` 문서의 본문 재작성

## 설계
- TTTM Spider URL build arg와 runtime env 전달을 제거한다.
- `env/web.common.env` 파일은 compose `env_file` 참조가 있으므로 파일은 유지하고 변수 라인만 제거한다.
- TTTM Spider iframe URL은 React page 상수 하나가 단일 소스가 된다.

## 실행 단계
- [x] active env/compose/Dockerfile/docs에서 TTTM Spider URL env 제거
- [x] grep으로 실행 계약에 남은 참조 확인
- [x] web lint와 compose config 검증 실행

## 검증
- `npm run lint` in `apps/web`
- `bash scripts/agent/check_compose_configs.sh`
- `rg -n "TTTM Spider URL env" env compose apps/web/Dockerfile apps/web/README.md docs/configuration.md`

## 위험과 대응
- 위험: compose가 빈 `env/web.common.env` 파일을 계속 참조한다.
- 대응: 파일은 삭제하지 않고 주석 파일로 유지한다.

## 진행 기록
- 2026-07-07: TTTM Spider URL 하드코딩 후 사용하지 않는 env 계약 제거 범위를 확인했다.
- 2026-07-07: TTTM Spider URL env 실행 계약을 제거하고 web lint, compose config, grep 검증을 통과했다.
