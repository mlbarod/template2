# ExecPlan: TTTM Spider embed

## 목표
- Apps 하위 메뉴에 TTTM Spider 항목을 추가한다.
- TTTM Spider 화면은 Portal shell 안에서 외부 TTTM Spider 앱을 iframe으로 임베드한다.
- 외부 URL은 TTTM Spider page 상수로 고정한다.

## 현재 상태
- `apps/web/src/lib/config/portalNavigation.js`가 Apps/About Us 하위 메뉴를 정의한다.
- `apps/web/src/routes/router.jsx`가 feature route facade를 모아 보호된 route를 구성한다.
- Portal 외부 링크 env는 `env/web.*.env`, `apps/web/Dockerfile`, `apps/web/README.md`에 문서화되어 있다.
- 2026-07-07 현재 TTTM Spider iframe URL은 env 계약에서 제거되고 page 상수로 고정되어 있다.

## 범위
- 수정: React web feature route/page, Portal navigation/branding.
- 제외: 백엔드 API, DB, auth 권한, 기존 Spider 기능의 동작 변경.

## 설계
- `apps/web/src/features/tttm-spider` feature를 추가하고 `index.js`에서 `tttmSpiderRoutes`만 named export한다.
- `/tttm_spider` route에서 고정 URL을 iframe `src`로 사용한다.
- 사용자 요청에 따라 TTTM Spider intranet URL은 코드에 직접 둔다.
- `portalNavigation.js` Apps 항목에는 내부 링크로 `TTTM Spider`를 추가한다.

## 실행 단계
- [x] ExecPlan 작성
- [x] TTTM Spider feature route/page 추가
- [x] Portal navigation/branding/router 연결
- [x] TTTM Spider iframe page 구현
- [x] frontend boundary/UI audit 실행

## 검증
- `scripts/agent/check_frontend_boundaries.sh`: 통과
- `scripts/agent/check_ui_consistency.sh`: 기존 `apps/web/src/features/l3-spider/components/L3SpiderSummaryView.jsx` raw color/inline style 후보로 실패
- `npm run web:build`: 통과
- `npm run web:lint`: 통과

## 위험과 대응
- 위험: iframe 대상 서버가 `X-Frame-Options` 또는 CSP로 임베드를 차단할 수 있다.
- 대응: 프론트엔드 route와 env 설정은 유지하되, 대상 서버의 frame 허용 정책은 별도로 확인한다.

## 진행 기록
- 2026-07-07: TTTM Spider 메뉴/임베드 추가 계획을 작성했다.
- 2026-07-07: `/tttm_spider` iframe route와 Apps 메뉴 항목을 추가하고 검증을 실행했다.
- 2026-07-07: TTTM Spider iframe URL을 env-driven 방식에서 코드 상수 방식으로 전환했다.
