# ExecPlan: L3 Spider 미매핑 line rule 진단

## 목표
- `line_name_rules.csv`에 매칭되지 않은 `line_id/process_id/step_seq` 조합을 개발자 옵션에서 확인한다.
- 개발 서버에서 로그인한 모든 사용자에게 해당 기능을 노출한다.
- integer `has_high_risk` 필터가 PostgreSQL 인덱스를 활용할 수 있게 조건식을 정리한다.

## 현재 상태
- 미매핑 조합은 `line_id`로 폴백되어 일반 화면에서 매칭 여부를 구분할 수 없다.
- 실제 분석 조합은 `public.l3_spider_daily_run_stats`에 있다.
- L3 Spider 헤더에는 메일 설정과 제외 필터 sheet action이 있다.

## 범위
- 미매핑 조합 조회 selector/service/API를 추가한다.
- L3 Spider 헤더에 개발자 옵션 sheet를 추가한다.
- 권한은 기존 L3 Spider와 동일하게 로그인 사용자로 한정한다.
- CSV 편집/업로드 기능은 추가하지 않는다.

## 설계
- PostgreSQL에서 조합별 최초/최근 날짜와 날짜 수를 집계한다.
- CSV 규칙이 명시적으로 매칭되었는지를 폴백 결과와 분리해 판정한다.
- React Query는 sheet가 열린 동안만 endpoint를 조회한다.
- 별도 migration과 env 변경은 없다.

## 실행 단계
- [x] 매칭 여부 판정과 PostgreSQL 진단 selector 추가
- [x] service/API 응답 계약과 테스트 추가
- [x] 개발자 옵션 sheet·API hook 추가
- [x] backend/frontend 테스트와 경계/UI audit

## 검증
- `docker compose exec -T api python manage.py test api.l3_spider --keepdb -v 1`
- `docker compose exec -T web npm run build`
- `npm run agent:audit:api-boundary`
- `npm run agent:audit:web-boundary`
- `npm run agent:audit:ui`
- `git diff --check`

## 위험과 대응
- 위험: 전체 `daily_run_stats` GROUP BY가 일반 화면 로딩을 느리게 할 수 있다.
- 대응: sheet 오픈 시에만 조회하고 진단 결과를 캐시한다.
- 위험: `line_name == line_id`로만 판정하면 명시적 동일 이름 매핑을 미매핑으로 오판한다.
- 대응: 규칙 hit 여부를 resolver에서 별도로 반환한다.

## 진행 기록
- 2026-07-13: 개발 서버 전용으로 모든 인증 사용자에게 노출하기로 확정.
- 2026-07-13: L3 Spider backend 테스트 30개와 frontend production build·ESLint 통과.
- 2026-07-13: backend/web boundary audit 통과. UI audit은 기존 `L3SpiderChart.jsx`의 raw HEX 6건만 보고.
