# ExecPlan: account card viewport height

## 목표
- account 페이지 요약 카드 아래 3개 카드가 남은 뷰포트 높이를 채우도록 조정한다.

## 현재 상태
- `apps/web/src/features/account/pages/AccountPage.jsx`는 요약 카드 아래 3열 그리드를 렌더링한다.
- `AffiliationCard`, `ManageableGroupsCard`, `AffiliationHistoryCard`는 `max-h-96` 때문에 부모 높이가 커져도 24rem에서 멈춘다.
- 계정 라우트 shell은 일반 account 페이지에서 `overflow-y-auto`를 사용한다.

## 범위
- 수정: account 페이지 wrapper/grid height, account 하위 3개 카드의 height/max-height 클래스, account route의 layout height class 전달.
- 제외: API, auth, route path, data fetching, table behavior, public facade.

## 설계
- 페이지 wrapper는 부모 shell의 `h-full`을 따르고 요약 카드는 `shrink-0` 영역으로 유지한다.
- 하단 카드 그리드는 `flex-1 min-h-0`으로 남은 높이를 받고, 큰 화면에서는 3열 내부 스크롤, 작은 화면에서는 1열 영역 스크롤을 사용한다.
- account route는 `AppShellLayout`을 통해 `SidebarInset`에 `h-full min-h-0 overflow-hidden`을 전달해 포털 헤더와 main padding이 이미 반영된 부모 높이를 따른다.
- account route inner wrapper는 `h-full min-h-0`을 사용하고, `/settings/account` 중간 wrapper인 `SettingsPage`도 fixed-height 대상으로 포함한다.
- 각 카드의 `max-h-96`을 제거하고 `h-full min-h-0`을 적용해 `CardContent`가 기존 `overflow-y-auto`를 유지한다.
- migration/env/auth 영향은 없다.

## 실행 단계
- [x] AccountPage의 loaded/loading 레이아웃 높이 구조를 조정한다.
- [x] 3개 account 카드 컴포넌트의 height 제한을 조정한다.
- [x] UI audit 또는 관련 검증을 실행한다.

## 검증
- `npm run agent:audit:ui`: 실패. 기존 `apps/web/src/features/l3-spider/components/L3SpiderChart.jsx` raw color/inline style 후보만 출력됨.
- `npm run web:lint`: 실패. 기존 `apps/web/src/features/l3-spider/components/L3SpiderSummaryView.jsx` 미사용 변수 `LINE_TOTAL_ITEMS`에서 중단됨.
- `npx eslint src/features/account/pages/AccountPage.jsx src/features/account/components/AffiliationCard.jsx src/features/account/components/ManageableGroupsCard.jsx src/features/account/components/AffiliationHistoryCard.jsx` (`apps/web` 기준): 통과.
- `npx eslint src/components/layout/AppShellLayout.jsx src/components/layout/AppLayout.jsx src/features/account/components/AccountSettingsShell.jsx src/features/account/pages/AccountPage.jsx src/features/account/components/AffiliationCard.jsx src/features/account/components/ManageableGroupsCard.jsx src/features/account/components/AffiliationHistoryCard.jsx` (`apps/web` 기준): 통과.

## 위험과 대응
- 위험: 모바일 1열에서 3개 카드가 한 화면 안에서 압축될 수 있다.
- 대응: 사용자가 요청한 화면 높이 채움을 우선하고, 필요 시 별도 모바일 스크롤 정책을 후속 조정한다.

## 진행 기록
- 2026-07-10: account 카드 3열 높이 확장 방향 확인.
- 2026-07-10: account 페이지와 카드 3개 컴포넌트 높이 구조 조정, account 범위 ESLint 통과.
- 2026-07-10: account route에서 `SidebarInset` 높이 class를 전달하도록 shared layout prop 추가.
- 2026-07-10: `/settings/account` 중간 wrapper height 누락을 수정하고, account page를 `shrink-0 + flex-1` 구조로 정리.
