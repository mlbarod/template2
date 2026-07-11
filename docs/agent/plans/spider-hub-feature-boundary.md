# ExecPlan: Spider 허브 feature boundary 정리

## 목표
- Spider 허브에서 L0/L1/L3/PM/TTTM 항목을 모두 보여주고, 권한이 없는 항목은 비활성 상태로 표시한다.
- 허브 페이지 소유 위치를 `fdc-trend`에서 `spider` feature로 옮긴다.

## 현재 상태
- `/spider` 허브는 글로벌 라우터에서 직접 붙어 있다.
- `/spider/l0`, `/spider/l1`은 각각 `l0-spider`, `l1-spider` 앱 권한 그룹 아래에 있어야 한다.
- L3/PM/TTTM 실제 화면은 각 앱 feature의 권한 그룹 아래에 있다.

## 범위
- 수정: Spider 허브 페이지, Spider feature facade/route, 글로벌 라우터 import, `fdc_trend` index redirect.
- 제외: backend 권한 판정, migration, 외부 Spider URL env 전환, L3/PM/TTTM 화면 내부 구현.

## 설계
- `apps/web/src/features/spider`를 허브 전용 feature로 추가한다.
- `/spider` route는 Portal 접근 후 접근 가능하게 두고, 허브 내부에서 각 앱 권한 상태를 표시한다.
- 권한이 있는 항목만 링크로 렌더링하고, 권한이 없는 항목은 `권한 없음` 배지와 lock icon이 있는 비활성 row로 렌더링한다.
- `fdc_trend` index는 feature 간 내부 import를 피하기 위해 `/spider`로 redirect한다.

## 실행 단계
- [x] `SpiderHomePage`를 `features/spider/pages`로 이동한다.
- [x] `features/spider/index.js`, `routes.jsx` public facade를 추가한다.
- [x] 글로벌 라우터가 `spiderRoutes`를 사용하게 정리한다.
- [x] `fdc-trend` index의 허브 직접 참조를 redirect로 바꾼다.
- [x] 허브 row를 전체 노출 + 비권한 표시 방식으로 바꾼다.
- [x] `/spider/l0`를 `features/spider/pages/L0SpiderPage.jsx` 하위 페이지로 분리한다.

## 검증
- `npx eslint`로 변경된 frontend 파일을 확인한다.
- `npm run agent:audit:web-boundary`로 feature boundary를 확인한다.
- `npm run agent:audit:ui`로 UI 규칙 후보를 확인한다.
- `npm run web:build`로 번들 빌드를 확인한다.

## 위험과 대응
- 위험: 새 `spider` feature 추가로 facade 누락이나 route import 누락이 생길 수 있다.
- 대응: `index.js`, `routes.jsx`를 모두 추가하고 boundary audit를 실행한다.
- 위험: 권한 없는 항목이 클릭 가능하면 backend gate까지 이동해 혼란이 생길 수 있다.
- 대응: 권한 없는 row는 링크 대신 비활성 `div`로 렌더링한다.

## 진행 기록
- 2026-07-11: Spider 허브를 `spider` feature로 옮기고 비권한 항목 표시 UX로 변경했다.
- 2026-07-11: 변경 파일 ESLint, frontend boundary audit, `git diff --check`, `npm run web:build` 통과를 확인했다.
- 2026-07-11: UI audit와 전체 web lint는 기존 L3 Spider 파일의 별도 후보/오류만 남아 있음을 확인했다.
- 2026-07-11: L0 Spider를 `l0-spider` feature 하위 페이지로 분리하고, `l0-spider` scope gate로 보호되도록 글로벌 라우터에서 route group을 구성했다.
