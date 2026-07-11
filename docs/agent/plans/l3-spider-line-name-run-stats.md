# ExecPlan: L3 Spider Line Name 분석 Step 집계

## 목표
- 동일 `line_id`가 여러 `line_name`으로 분리되어도 Summary의 분석 `step_seq` 수를 정확히 표시한다.

## 현재 상태
- 위험 집계는 `(line_id, process_id, step_seq)` 규칙으로 `line_name`을 정확히 계산한다.
- 실행 통계는 `line_id`별 집계 후 하나의 `line_name`으로 치환해 다른 `line_name`이 누락된다.
- SQLite의 위험 행과 `daily_run_stats`에는 `step_seq`가 정상 저장되어 있다.

## 범위
- 일별 Summary 응답에 `line_name`별 실행 통계를 추가한다.
- 프론트 Summary가 새 집계를 우선 사용하도록 변경한다.
- SQLite schema와 알고리즘 서버 데이터 계약은 변경하지 않는다.

## 설계
- 기존 `runStats.byLine`은 하위 호환을 위해 유지한다.
- Summary 집계에 이미 사용한 `file_df`에서 `line_name`별 distinct `step_seq`와 `row_cnt`를 계산해 `runStats.byLineName`으로 반환한다.
- 프론트는 `byLineName`이 있으면 사용하고, 구버전 API에서는 `byLine`으로 fallback한다.

## 실행 단계
- [x] 백엔드 `line_name`별 실행 통계 집계 추가
- [x] 프론트 집계 선택 로직 변경
- [x] 동일 Line ID의 다중 Line Name 회귀 테스트 추가
- [x] 백엔드/프론트 검증

## 검증
- `docker compose exec -T api python manage.py test api.l3_spider --keepdb -v 1`
- `npx eslint src/features/l3-spider/components/L3SpiderSummaryView.jsx`
- `npm run agent:audit:api-boundary`
- `npm run agent:audit:web-boundary`
- `git diff --check`

## 위험과 대응
- 위험: 기존 소비자가 `runStats.byLine` 계약에 의존할 수 있다.
- 대응: 기존 필드는 유지하고 정확한 신규 필드를 추가한다.
- 위험: 제외 필터 적용 시 실행 통계와 화면 집계 범위가 달라질 수 있다.
- 대응: 화면에 실제 반영된 `file_df`에서 새 통계를 계산해 Summary와 동일한 범위를 사용한다.

## 진행 기록
- 2026-07-11: SQLite 원본 정상 및 `line_id` 단일 치환 문제 확인, 구현 시작.
- 2026-07-11: `runStats.byLineName` 추가와 프론트 fallback 적용, L3 Spider 테스트 21개 통과.
- 2026-07-11: 실제 2026-06-17 데이터에서 위험 라인 6개 모두 분석 step 집계 확인.
- 2026-07-11: 프론트 lint와 양쪽 경계 검사는 통과. 전체 빌드는 기존 Observer CSS import 오류로 실패.
