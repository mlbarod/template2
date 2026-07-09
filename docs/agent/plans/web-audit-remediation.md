# ExecPlan: Web audit remediation

## 목표
- `apps/web` npm audit에서 보고된 취약점을 의존성 갱신으로 해소한다.

## 현재 상태
- `apps/web/package.json`은 React/Vite 기반 SPA 의존성을 관리한다.
- `apps/web/package-lock.json`은 Docker web context에서 사용된다.
- 루트 `package-lock.json`은 npm workspace 명령에서 사용된다.
- 현재 audit 결과는 low 2, moderate 5, high 10, total 17이다.

## 범위
- 수정할 영역: `apps/web/package.json`, `apps/web/package-lock.json`, 루트 `package-lock.json`
- 수정하지 않을 영역: 프론트엔드 기능 코드, API/DB/auth/env contract, `pnpm-lock.yaml`

## 설계
- 먼저 SemVer 호환 가능한 npm audit fix와 명시적 dependency update를 적용한다.
- 남는 취약점이 있으면 해당 direct dependency만 좁게 조정한다.
- public API/facade, migration, env, auth 영향은 없다.

## 실행 단계
- [x] 취약 direct dependency의 최신/수정 가능 버전을 확인한다.
- [x] npm으로 web dependency와 lockfile을 갱신한다.
- [x] standalone web lockfile도 Docker context 기준으로 갱신한다.

## 검증
- `npm audit --workspace web`
- `npm audit --workspaces=false` from `apps/web`
- `npm run build --workspace web`

## 위험과 대응
- 위험: `quill` audit fix가 downgrade를 요구할 수 있다.
- 대응: audit 결과와 빌드 검증을 기준으로 최소 변경을 선택한다.

## 진행 기록
- 2026-07-09: audit 취약점 해소 작업 시작.
- 2026-07-09: `vite`, `react-router-dom`, `dompurify`, `react-use`, `quill` resolved version을 갱신하고 audit/build 검증을 통과했다.
