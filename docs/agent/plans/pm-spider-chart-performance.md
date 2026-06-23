# ExecPlan: PM Spider chart performance

## 목표
- PM Spider TRACE/OES 상세 차트를 큰 데이터에서도 빠르게 표시한다.
- 원본 raw/score parquet schema는 유지하고 API 응답에 차트용 파생 구조를 추가한다.
- SVG/DOM 대량 렌더링 대신 Canvas와 downsampled/heatmap matrix 응답을 사용한다.

## 현재 상태
- Backend: `apps/api/api/pm_comparison/services/__init__.py`가 raw parquet를 row object list로 변환해 `trendRows`, `trajectoryRows`를 반환한다.
- Frontend: `apps/web/src/features/pm-spider/components/PmSpiderCategoryDashboard.jsx`가 Recharts line chart와 React DOM heatmap grid를 사용한다.
- 최악 케이스는 TRACE `50 x 1800`, OES heatmap `1200 x 100`, OES wavelength detail `50 x 18000`이다.

## 범위
- 수정 영역:
  - `apps/api/api/pm_comparison/serializers.py`
  - `apps/api/api/pm_comparison/services/__init__.py`
  - `apps/api/api/pm_comparison/tests.py`
  - `apps/web/src/features/pm-spider/components/*`
  - `apps/web/src/features/pm-spider/hooks/usePmSpiderQueries.js`
- 수정하지 않는 영역:
  - raw/score parquet 파일 schema
  - mount/env/auth contract
  - unrelated chart style debt

## 설계
- API request에 `maxPoints`, `xStart`, `xEnd`, `heatmapXBins`, `heatmapYBins`를 추가한다.
- TRACE 상세 응답에 `trace.lineChart`를 추가한다.
- OES step 상세 응답에 `oes.heatmap`을 추가하고, wavelength 선택 응답에는 `oes.lineChart`, `oes.spectrumChart`를 추가한다.
- 큰 detail row list는 frontend fallback에 필요한 수준으로만 유지하고, Canvas는 chart 전용 응답을 우선 사용한다.
- DB migration/env/auth 변경은 없다.

## 실행 단계
- [x] Serializer request field 추가
- [x] Backend downsample/heatmap builder 추가
- [x] Backend tests 추가/수정
- [x] Frontend Canvas line/heatmap 컴포넌트 추가
- [x] PM detail 화면에서 Canvas 응답 우선 사용
- [x] 검증 실행

## 검증
- 통과: `git diff --check`
- 통과: `docker compose -f docker-compose.dev.yml exec -T api python manage.py test api.pm_comparison`
- 통과: `npm run agent:audit:api-boundary`
- 통과: `npm run agent:audit:web-boundary`
- 실패: `npm run web:build` (`vite: not found`)
- 실패: `npm run web:lint` (`eslint: not found`)
- 실패: `npm run agent:audit:ui` (기존 raw color/inline style 후보)

## 위험과 대응
- 위험: 기존 tests가 row list shape에 의존한다.
- 대응: 기존 field는 유지하되 큰 데이터에서는 chart field를 우선 사용하게 한다.
- 위험: Canvas chart가 기존 Recharts 기능 일부를 단순화할 수 있다.
- 대응: zoom/legend/toggle/close 등 주요 UX는 유지하고, 복잡한 SVG-only 장식은 fallback 범위로 둔다.

## 진행 기록
- 2026-06-19: 사용자 요청에 따라 full performance path 구현 시작. 원본 parquet schema 변경 없이 API 파생 응답과 Canvas rendering으로 설계.
- 2026-06-19: `maxPoints`, `xStart/xEnd`, heatmap bin 옵션과 `lineChart`/`heatmap`/`spectrumChart` 응답 추가. TRACE raw/OES heatmap/OES wavelength detail을 Canvas 우선 렌더링으로 연결.
- 2026-06-19: Backend PM comparison test와 boundary audit는 통과. Frontend build/lint는 local dependency executable 부재로 실행 실패, UI audit는 기존 style debt 후보로 실패.
