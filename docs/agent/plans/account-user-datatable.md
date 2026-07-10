# ExecPlan: Account 사용자 데이터테이블 통일

## 목표
- `@ss-blocks/datatable-component-04` 디자인을 Members와 Permissions 사용자 목록에 적용한다.
- 기존 API, React Query, 탭, 필터, 페이지 이동, 승인/권한 작업을 유지한다.
- 두 화면이 동일한 사용자 식별, 테이블 툴바, 열 밀도, empty/loading/error 패턴을 사용하게 한다.

## 현재 상태
- Members는 소속 멤버와 승인 요청을 클라이언트에서 행으로 변환해 공용 Table로 표시한다.
- Permissions는 서버 페이지네이션 결과를 인원별 권한 및 승인 대기 탭에서 표시한다.
- `@tanstack/react-table`은 이미 web 의존성에 포함되어 있다.
- 권한 관리 화면에는 별도의 필터와 상태별 행 작업이 구현되어 있다.

## 범위
- 수정할 영역: `apps/web/src/features/account/components`, Members/Permissions page와 고정 목록 레이아웃.
- 유지할 영역: account API 응답, React Query hook, 권한 판정, mutation, backend 계약.
- 블록의 예제 데이터와 제품에 필요 없는 데모 기능은 최종 화면에 포함하지 않는다.

## 설계
- registry block의 column header, toolbar, row density, action menu, 숫자 pagination 패턴을 저장소 JSX/Tailwind 규칙에 맞게 이식한다.
- account feature 내부에 사용자 목록용 재사용 데이터테이블을 두고 각 page가 column과 row action을 주입한다.
- Members의 전체 멤버와 서버 페이지 요청 결합 방식, Permissions의 서버 필터/페이지네이션 소유권은 각 page에 유지한다.
- public facade와 backend/auth/env 계약은 변경하지 않는다.

## 실행 단계
- [x] shadcn block 설치 시도 및 공개 preview/의존성 검토
- [x] account 사용자 데이터테이블 공통 컴포넌트 구성
- [x] Members 사용자 목록 적용
- [x] Permissions 사용자 목록과 승인 대기 목록 적용
- [x] lint/build/audit 및 desktop/mobile 상호작용 검증

## 검증
- 변경 프론트 파일 대상 ESLint
- `npm run web:build`
- `npm run agent:audit:web-boundary`
- `npm run agent:audit:ui`
- Playwright로 Members/Permissions desktop/mobile 화면과 주요 행 작업 확인
- `git diff --check HEAD`

## 위험과 대응
- 위험: block의 client pagination이 Permissions 서버 페이지네이션과 충돌할 수 있다.
- 대응: 서버 pagination은 page가 소유하고 block에는 현재 page의 rows만 전달한다.
- 위험: registry가 기존 UI primitive를 덮어쓸 수 있다.
- 대응: 생성 전후 diff를 확인하고 기존 변경을 보존하며 필요한 파일만 채택한다.
- 위험: Members와 Permissions의 행 action 계약이 다르다.
- 대응: 공통 컴포넌트는 렌더링과 table state만 담당하고 action은 column 정의에 남긴다.

## 진행 기록
- 2026-07-10: 사용자 요청, 현재 두 목록의 데이터 소유권, shadcn 설정과 TanStack Table 의존성을 확인했다.
- 2026-07-10: `shadcn@latest`와 CLI 권장 호환 버전 설치는 registry의 `style: blocks` 라우팅 오류로 실패했으며 저장소 파일은 생성되지 않았다.
- 2026-07-10: 공식 live preview와 block metadata에서 filter shell, 2줄 사용자 identity, 상태 badge, compact action, 숫자 pagination 구성을 확인했다.
- 2026-07-10: bulk API와 ordering 계약이 없어 예제 checkbox/client sorting은 제외하고 기존 서버 페이지네이션을 유지하기로 했다.
- 2026-07-10: 공통 `AccountDataTable`과 도메인별 column/action 구성을 적용하고 Members와 Permissions의 사용자 목록을 동일한 밀도와 상태 표현으로 통일했다.
- 2026-07-10: Members의 요청 목록은 `page/pageSize/totalPages` 서버 계약으로 고정하고 숫자 페이지 이동과 페이지 크기 변경을 브라우저에서 검증했다.
- 2026-07-10: 대상 ESLint, production build, `git diff --check`, Members/Permissions Playwright 검증이 통과했다. 저장소 audit는 기존 `dashboard-template`, `l3-spider` 후보만 보고했다.
