# ExecPlan: home legacy cleanup

## 목표
- `apps/web/src/features/home`에 남은 미사용 이전 구현 잔재를 제거한다.

## 현재 상태
- 전역 네비게이션은 `apps/web/src/components/layout/PortalGlobalShell.jsx`와 `apps/web/src/lib/config/portalNavigation.js`를 사용한다.
- `features/home` 내부에 정적 참조가 없는 이전 home navbar/team wrapper 코드가 남아 있다.

## 범위
- 수정: `apps/web/src/features/home/**`의 미사용 파일, export, props 정리
- 수정: 이 작업 기록용 ExecPlan 파일
- 제외: 현재 동작 중인 `components/layout` portal shell, 라우트 구조, 다른 feature 변경

## 설계
- import 검색으로 참조가 없는 파일만 삭제한다.
- `homeRoutes`처럼 실제 라우터에서 소비되는 public facade는 유지한다.
- layout 계층의 `PortalHomeShell`, `PortalGlobalShell`, `PortalNavbar`는 유지한다.
- API/DB/auth/env 변경은 없다.

## 실행 단계
- [x] 미사용 후보와 참조 경로 확인
- [x] 확정된 legacy 파일/export/props 제거
- [x] frontend boundary와 관련 lint 검증

## 검증
- `rg`로 삭제 대상 참조가 남지 않았는지 확인한다.
- `scripts/agent/check_frontend_boundaries.sh`
- 변경 관련 파일 대상 ESLint
- 전체 `npm run web:lint`와 `npm run web:build`는 기존 `apps/web/vite.config.mjs` 오류가 막는지 확인한다.

## 위험과 대응
- 위험: 공개 facade export 삭제로 외부 참조가 깨질 수 있다.
- 대응: 저장소 전체 `rg`로 참조가 없는 export만 제거하고, 실제 라우터 export는 유지한다.

## 진행 기록
- 2026-07-07: home legacy 잔재 추가 확인 및 제거 계획 작성.
- 2026-07-07: 미사용 home navbar, team mock section, layout wrapper, 미소비 hero actions 정리.
- 2026-07-07: frontend boundary audit, 관련 파일 ESLint, 전체 web lint/build 통과.
