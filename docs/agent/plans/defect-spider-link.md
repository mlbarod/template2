# ExecPlan: Defect Spider 링크 추가

## 목표
- `/spider` 허브 화면에 Defect Spider 링크를 추가한다.
- 6개 Spider 링크가 기존 카드 높이 안에서 답답하지 않게 보이도록 링크 row를 조정한다.

## 현재 상태
- `/spider` 허브는 `apps/web/src/features/spider/pages/SpiderHomePage.jsx`에서 링크 목록을 정의한다.
- 카드/시각 영역은 `apps/web/src/features/spider/components/SpiderBentoAppCards.jsx`에서 렌더링한다.
- 외부 URL은 `VITE_*` 환경변수 패턴을 사용한다.

## 범위
- 수정: Spider 허브 링크 목록, 카드 레이아웃 크기, Defect Spider URL 환경변수 문서/환경 파일.
- 제외: backend API, DB, 권한 모델 변경.

## 설계
- `/spider` 허브 카드에는 same-origin `/spider/defect` route를 사용한다.
- `/spider/defect` route에서 `VITE_DEFECT_SPIDER_URL`을 읽어 외부 HTTP 앱으로 redirect한다.
- Defect Spider는 별도 app access scope가 없으므로 `/spider` 허브 접근 사용자를 대상으로 노출한다.
- 카드 시각 영역 높이는 기존 값을 유지하고 링크 stack의 row 높이와 간격을 줄인다.

## 실행 단계
- [x] Defect Spider URL 환경변수 추가
- [x] Spider 링크 목록에 Defect Spider 항목 추가
- [x] Spider 카드 크기와 링크 ref 수 조정
- [x] lint/audit 검증

## 검증
- `npm run web:lint`
- `npm run agent:audit:ui`
- `npm run agent:audit:web-boundary`

## 위험과 대응
- 위험: 운영 정적 빌드에서 Vite 환경변수는 빌드 시점 값만 반영된다.
- 대응: Dockerfile/Compose build args와 env 문서를 함께 갱신한다.

## 진행 기록
- 2026-07-13: `/spider` 허브와 env-driven 외부 링크 패턴 확인 후 계획 작성.
- 2026-07-13: `VITE_DEFECT_SPIDER_URL`을 Web 공통 env, Dockerfile build env, prod Compose build args, 설정 문서에 추가.
- 2026-07-13: Defect Spider 링크 항목을 추가하고 6개 링크 기준 card/link stack 높이, 폭, 간격을 조정.
- 2026-07-13: `npm run web:lint`, `npm run web:build`, `npm run agent:audit:web-boundary` 통과. `npm run agent:audit:ui`는 기존 `L3SpiderChart.jsx` raw color/inline style 후보로 실패. `npm run agent:audit:docs`는 기존 미추적 `grant_initial_access` command 색인 누락으로 실패.
- 2026-07-13: `/spider` 허브 DOM에 직접 `http://` 링크가 노출되지 않도록 Defect Spider를 `/spider/defect` redirect route로 분리.
