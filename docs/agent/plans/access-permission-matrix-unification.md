# ExecPlan: Portal·앱 권한 매트릭스 통합

## 목표
- Portal과 앱 권한을 하나의 사용자별 권한 매트릭스에서 관리한다.
- 중복된 인원별 권한 탭과 상태·결정 기준 필터를 제거한다.
- Portal의 승인 요청, 역할, 거절 사유와 감사 로그 의미는 보존한다.
- 페이지네이션 footer 없이 스크롤에 따라 다음 사용자 페이지를 이어서 불러온다.

## 현재 상태
- `/api/v1/account/access/matrix`는 Portal과 활성 앱 scope 13개를 페이지 단위로 반환한다.
- 권한 매트릭스 조회 훅은 첫 페이지와 하단 페이지네이션을 사용하는 `useQuery` 구조다.
- 저장소에는 `useInfiniteQuery`와 scroll-end 로딩을 사용하는 기존 account 패턴이 있다.

## 범위
- account 매트릭스 API 응답에 Portal scope를 첫 번째 열로 추가한다.
- 권한 관리 화면에서 인원별 권한 탭과 전용 필터/query 상태를 제거한다.
- Portal 셀은 기존 결정 다이얼로그를 재사용하고 앱 셀은 즉시 변경을 유지한다.
- 승인 대기, 자동 접근 규칙, 변경 이력 탭은 유지한다.
- 매트릭스 footer를 제거하고 기존 페이지 API를 무한 스크롤 방식으로 소비한다.
- DB schema, migration, API URL은 변경하지 않는다.

## 설계
- 매트릭스 scope 순서는 `portal` 다음 활성 앱 이름순으로 고정한다.
- Portal의 대기 상태를 허용/차단하면 각각 `approve`/`reject`를 호출한다.
- Portal의 일반 허용/차단은 `grant`/`revoke`, 역할 수정은 `change_role`을 호출한다.
- Portal의 수동 설정 해제는 `reset_to_policy`를 호출한다.
- Portal 변경은 역할 또는 사유 확인이 필요한 기존 결정 다이얼로그를 거친다.
- 상단 사용자·자동 허용 요약은 현재까지 불러온 매트릭스 행에서 계산한다.
- 필터와 페이지 크기를 infinite query key에 포함하고 다음 페이지는 응답의 pagination으로 결정한다.
- 테이블 스크롤이 하단 96px 이내에 도달하면 중복 요청을 막은 상태로 다음 페이지를 요청한다.

## 실행 단계
- [x] 기존 매트릭스와 인원별 권한 기능 대응표를 확인한다.
- [x] 매트릭스 API에 Portal scope를 추가하고 계약 테스트를 수정한다.
- [x] Portal 셀 상호작용과 역할 변경 진입점을 추가한다.
- [x] 인원별 권한 탭, 중복 필터와 query 상태를 제거한다.
- [x] 백엔드·프론트엔드 자동 검증을 실행한다.
- [x] 데스크톱·모바일 및 Portal 상태 전이를 브라우저에서 검증한다.
- [x] 매트릭스 조회를 누적형 infinite query로 전환한다.
- [x] 페이지네이션 footer를 제거하고 scroll-end 로딩 상태를 추가한다.
- [x] 20명 초과 응답의 누적 로딩과 필터 초기화를 브라우저에서 검증한다.

## 검증
- `docker compose exec -T api python manage.py test api.account api.auth`
- `docker compose exec -T api python manage.py makemigrations --check --dry-run`
- 변경 frontend 파일 ESLint와 `npm run build`
- frontend/backend boundary, UI consistency, docs inventory audit
- Playwright에서 Portal 열, 탭 구성, 역할 다이얼로그, 승인·거절 상태 전이와 overflow 확인
- Playwright mock 응답에서 20명 이후 페이지가 스크롤 시 누적되고 footer가 없는지 확인

## 위험과 대응
- 위험: Portal 대기 상태를 `grant/revoke`로 처리하면 감사 로그 의미가 바뀐다.
- 대응: 현재 상태가 pending이면 반드시 `approve/reject`로 매핑한다.
- 위험: 앱과 달리 Portal은 역할을 가지므로 단일 상태 Select만으로 기능이 축소된다.
- 대응: 허용된 Portal 셀에 역할 변경 버튼을 제공하고 기존 다이얼로그를 재사용한다.
- 위험: 인원별 query 제거로 상단 요약이 비거나 오래될 수 있다.
- 대응: 항상 활성화된 매트릭스 query의 pagination과 현재까지 누적한 Portal 판정으로 요약한다.
- 위험: footer만 제거하면 첫 20명 이후 사용자에 접근할 수 없다.
- 대응: API 계약은 유지하면서 infinite query와 scroll-end 로딩을 함께 적용한다.

## 진행 기록
- 2026-07-11: 사용자 요청에 따라 Portal·앱 권한 매트릭스 통합을 시작했다.
- 2026-07-11: DB 변경 없이 기존 matrix·decision API 확장으로 구현 가능함을 확인했다.
- 2026-07-11: matrix API가 Portal을 첫 scope로 반환하고 Portal 역할과 앱 boolean 계약을 함께 유지하도록 확장했다.
- 2026-07-11: 인원별 탭과 상태·결정 기준 필터를 제거하고 Portal을 첫 열로 포함한 단일 권한 매트릭스를 구현했다.
- 2026-07-11: Portal pending의 approve/reject, 역할 변경, 앱 grant/reset 감사 액션을 실제 브라우저와 DB에서 확인했다.
- 2026-07-11: 1440px와 390px viewport에서 document overflow가 없고 모바일 작업 탭이 동일 폭으로 표시됨을 확인했다.
- 2026-07-11: account/auth 161개 테스트, 변경 frontend lint, production build, migration·무결성, 경계·문서 감사를 통과했다.
- 2026-07-11: 전체 web lint의 기존 L3 Spider 미사용 상수 1건과 UI 감사의 기존 L3 차트 후보 6건은 요청 범위 밖 잔여 항목으로 유지했다.
- 2026-07-11: Account API와 모듈 문서에 Portal 우선 매트릭스 응답과 지원 결정 액션을 반영했다.
- 2026-07-11: 페이지네이션 footer 제거 요청을 실제 무한 스크롤 전환으로 처리하기로 결정했다.
- 2026-07-11: 22명 모의 응답에서 1페이지 20명 이후 2페이지 2명이 누적되고 footer가 렌더링되지 않음을 확인했다.
- 2026-07-11: 검색 적용 시 infinite query가 1페이지부터 다시 시작하고 이전 누적 행을 교체함을 확인했다.
