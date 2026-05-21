# 프론트엔드 상세 구조

`apps/web`은 React 19, React Router 7, Vite 6, Tailwind CSS 4 기반 SPA입니다. 서버 데이터는 React Query, UI 상호작용 상태는 feature-local Zustand/store 또는 component state가 담당합니다.

## 실행 단위

| 항목 | 값 |
| --- | --- |
| Framework | React 19, React Router 7 |
| Build | Vite 6 |
| Style | Tailwind CSS 4, shadcn/Radix primitives |
| 서버 데이터 | React Query |
| UI 상태 | Zustand 또는 component state |
| 로컬 실행 | `npm run web:dev` |

## 최상위 구조

| 경로 | 역할 |
| --- | --- |
| `apps/web/src/routes/router.jsx` | 전역 route 조립 |
| `apps/web/src/components/layout` | 전역 shell/layout |
| `apps/web/src/components/common` | 여러 feature에서 쓰는 공통 UI |
| `apps/web/src/components/ui` | shadcn/Radix 기반 primitive |
| `apps/web/src/features/<feature>` | feature별 page/component/hook/api/store/utils |
| `apps/web/src/lib` | API helper, auth, query client, theme 같은 공통 library |

## Feature 경계

각 feature는 다음 subpath만 사용합니다.

| Subpath | 역할 |
| --- | --- |
| `routes.jsx` | feature route 배열 |
| `index.js` | 외부 공개 facade |
| `pages/` | route에 직접 매핑되는 page |
| `components/` | feature 내부 UI component |
| `hooks/` | feature 내부 query/state/interaction hook |
| `api/` | backend endpoint client와 query key |
| `store/` | feature-local UI 상태 |
| `utils/` | feature 내부 pure helper |

다른 feature에서 import할 때는 `@/features/<feature>` facade만 사용합니다.

## Route tree

| Feature | Route | 설명 |
| --- | --- | --- |
| `home` | `/` | 인증 후 홈 shell |
| `auth` | `/login` | 로그인 화면 |
| `account` | `/settings/account`, `/settings/members` | 내 계정, 소속, 멤버/권한 관리 |
| `emails` | `/emails/inbox`, `/emails/sent`, `/emails/members` | 받은 메일, 보낸 메일, mailbox member |
| `assistant` | `/assistant` | RAG 기반 채팅 |
| `line-dashboard` | `/ESOP_Dashboard`, `/ESOP_Dashboard/status/:lineId`, `/ESOP_Dashboard/history/:lineId`, `/ESOP_Dashboard/settings/:lineId`, `/ESOP_Dashboard/settings/notification/:lineId`, `/ESOP_Dashboard/settings/recipients/:lineId`, `/ESOP_Dashboard/overview` | Drone SOP 현황/이력/설정 |
| `l3-spider` | `/l3_spider` | EDS Parquet 기반 반도체 이상감지 대시보드 |
| `timeline` | `/timeline`, `/timeline/:eqpId` | 설비 로그 timeline |
| `appstore` | `/appstore` | 내부 앱 목록/등록/댓글 |
| `voc` | `/voc` | VOC 게시판 |
| `teamstaff` | `/teamstaff` | 팀/인력 보조 화면 |
| `errors` | `*` | 404와 route error |

## API 호출 흐름

1. Page가 feature hook을 호출합니다.
2. Hook이 React Query query/mutation을 구성합니다.
3. API client가 `VITE_BACKEND_URL` 또는 상대 `/api/v1/**` endpoint를 호출합니다.
4. 성공 응답은 React Query cache에 남고, UI 상태만 store/component state에 저장합니다.
5. write mutation은 필요한 최소 scope만 invalidate합니다.

## 상태 관리 원칙

| 상태 유형 | 저장 위치 |
| --- | --- |
| 서버에서 온 목록/상세/권한 | React Query |
| 선택된 row, 필터 panel open 여부, tab, drawer 상태 | component state 또는 Zustand |
| 로그인 사용자 | auth provider/hook |
| route parameter | React Router |
| theme/layout shell 상태 | 공통 layout/lib |

서버 데이터를 Zustand에 복제하지 않습니다.

## UI와 레이아웃 원칙

- page skeleton은 `h-screen flex flex-col`과 `flex-1 min-h-0 overflow-hidden` 구조를 우선합니다.
- scroll 영역은 region마다 축별 하나만 둡니다.
- Tailwind semantic token을 먼저 사용하고 raw HEX/inline style은 피합니다.
- loading, empty, error, disabled, selected, focus 상태를 명시합니다.
- `apps/web/src/components/ui/**`는 shadcn CLI 흐름 또는 명시 요청 없이 직접 수정하지 않습니다.

## 변경 시 갱신해야 하는 문서

- route 추가/변경: `docs/inventory.md`, `docs/frontend.md`, 해당 `docs/modules/*.md`
- API client 변경: 해당 `docs/api/*.md`, 해당 `docs/modules/*.md`
- feature facade 변경: `docs/frontend.md`, 필요 시 boundary audit 결과
- 주요 화면 흐름 변경: 해당 `docs/modules/*.md`
