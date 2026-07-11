# ExecPlan: 권한 관리 UX 후속 개선

## 목표
- Spider 허브와 포털 메뉴를 앱별 권한에 맞게 노출한다.
- 권한 관리 화면에서 Portal뿐 아니라 앱별 자동 접근 규칙을 관리한다.
- 권한 변경 대상 사용자의 열린 UI가 짧은 시간 안에 최신 상태를 반영한다.

## 현재 상태
- Portal 메뉴의 Spider 항목은 Spider 하위 앱 scope 전체를 검사한다.
- Spider 허브는 L0/L1/L3/PM/TTTM 항목을 권한과 무관하게 모두 표시한다.
- 자동 접근 규칙 API는 앱 scope를 지원하지만 UI는 `portal`로 고정되어 있다.
- 권한 mutation은 작업자 세션만 갱신하며 다른 활성 세션은 긴 세션 갱신 주기에 의존한다.

## 범위
- 수정: `apps/web/src`의 Spider 라우트/허브, 포털 메뉴 판정, 권한 관리 UI, 인증 상태 갱신.
- 제외: migration reverse, 외부 Spider 서버 인증, 외부 URL 환경변수화.

## 설계
- Spider 메뉴는 관련 scope 중 하나라도 허용되면 표시한다.
- `/spider` 허브는 특정 앱 gate 밖에서 Portal gate만 적용하고, 각 링크를 scope별로 필터링한다.
- 자동 접근 규칙은 선택한 scope로 조회/생성하며 앱 scope에는 role을 전송하지 않는다.
- `/auth/me`는 화면이 보이는 활성 세션에서 30초마다 갱신하고, 현재 작업자 상태는 mutation 직후 갱신한다.
- API/DB/migration 계약은 변경하지 않는다.

## 실행 단계
- [x] Spider 메뉴와 허브의 scope 판정을 정렬한다.
- [x] 자동 접근 규칙에 scope 선택과 앱 boolean 정책 UX를 추가한다.
- [x] 인증 상태의 활성 세션 갱신 주기를 추가한다.
- [x] lint/build/boundary/UI 검증을 실행한다.

## 검증
- `npm run web:lint`
- `npm run web:build`
- `npm run agent:audit:web-boundary`
- `npm run agent:audit:ui`
- `git diff --check`

## 위험과 대응
- 위험: `/auth/me` 주기 호출로 불필요한 부하가 생길 수 있다.
- 대응: 문서가 보이는 인증 세션만 30초 주기로 갱신하고 숨김 탭에서는 호출하지 않는다.
- 위험: 앱 정책에 Portal role을 잘못 전송할 수 있다.
- 대응: 앱 scope payload에서는 role 필드를 생략하고 UI도 역할 대신 단순 허용으로 표시한다.

## 진행 기록
- 2026-07-11: 사용자 선택에 따라 리뷰 항목 2, 4, 5만 개선하기로 확정했다.
- 2026-07-11: Spider 권한별 노출, 앱 정책 scope 선택, 활성 세션 30초 갱신을 구현했다.
- 2026-07-11: 변경 파일 lint, production build, frontend boundary, docs audit, diff 검사를 통과했다. 전체 lint/UI audit는 기존 L3 Spider 후보로 실패했다.
