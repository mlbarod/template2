# ExecPlan: PM Spider OES Detail Latency

## 목표
- PM Spider OES 상세 차트가 더 빨리 표시되도록 초기 step heatmap과 wavelength trajectory 요청의 불필요한 계산/응답을 줄인다.
- 기존 API 응답 필드는 유지하고, 새 옵션을 보내지 않는 호출은 기존 동작을 유지한다.
- OES 예시 raw 데이터를 실제 운영 규모인 `35,902,694 points -> 1200 x 100 matrix`에 맞춘다.

## 현재 상태
- OES step 상세 요청은 heatmap 표시 전에도 spectrum chart와 detail row를 함께 생성한다.
- wavelength trajectory 요청은 line chart 표시 전에도 heatmap을 다시 생성한다.
- 실제 mock 기준 heatmap x-bin 1200은 약 4.8MB 응답이며 800으로 낮추면 약 3.7MB로 줄어든다.
- 기존 mock raw는 선택 step 기준 `7,206,000 points -> 800 x 80 matrix`로 실제 OES 규모보다 작다.

## 범위
- 수정 영역:
  - `apps/api/api/pm_comparison/serializers.py`
  - `apps/api/api/pm_comparison/services/__init__.py`
  - `apps/api/api/pm_comparison/tests.py`
  - `apps/web/src/features/pm-spider/hooks/usePmSpiderQueries.js`
  - `apps/web/src/features/pm-spider/components/PmSpiderCategoryDashboard.jsx`
- 수정하지 않는 영역:
  - raw/score parquet schema
  - DB schema/migration
  - auth/env/compose contract
  - 시각 스타일 리디자인

## 설계
- 요청 옵션 `includeOesHeatmap`, `includeOesSpectrum`을 추가한다.
- 요청 옵션 `includeTraceDetails`, `includeOesDetails`를 추가해 대상이 아닌 raw 상세 계산을 건너뛴다.
- backend 기본값은 둘 다 `True`로 둬 기존 호출 호환성을 유지한다.
- frontend step heatmap 요청은 `includeOesSpectrum=false`, `limit=50`, `heatmapXBins=1200`으로 보낸다.
- frontend wavelength trajectory 요청은 `includeOesHeatmap=false`로 보낸다.
- spectrum 탭을 열 때만 `includeOesSpectrum=true` payload로 다시 조회한다.
- mock OES는 선택 step에서 3개 cycle 합산 29,894 row와 1,201 wavelength column이 되도록 time point를 398~399개로 생성한다.
- frontend step heatmap 요청은 실제 matrix 크기에 맞춰 `heatmapXBins=1200`, `heatmapYBins=100`을 사용한다.
- backend는 선택 step이 있을 때 Parquet `rcp_step` filter를 먼저 적용하고, heatmap bin 평균은 NumPy 배열에서 계산한다.

## 실행 단계
- [x] serializer request option 추가
- [x] OES service에서 heatmap/spectrum 선택 생성 적용
- [x] detail 대상이 아닌 trace/OES raw 상세 계산 skip 적용
- [x] frontend detail hook에 옵션 전달 구조 추가
- [x] OES step/wavelength 호출 옵션 조정
- [x] service 회귀 테스트 추가/수정
- [x] 성능과 테스트 검증
- [x] mock OES raw 규모 확대
- [x] 선택 step Parquet filter와 heatmap 계산 경로 최적화
- [x] 실제 mock 조건으로 로딩 시간 재측정

## 검증
- 통과: `python3 -m py_compile make_pm_spider_raw_mock.py apps/api/api/pm_comparison/selectors.py apps/api/api/pm_comparison/services/__init__.py apps/api/api/pm_comparison/tests.py`
- 통과: `docker compose -f docker-compose.dev.yml exec -T api python manage.py test api.pm_comparison`
- 통과: 실제 mock 조건 OES heatmap service 2.4~2.5초, JSON 직렬화 0.16초, 응답 약 3.9MB
- 통과: 실제 mock 조건 OES trajectory-only service 0.818초
- 통과: `git diff --check`
- 통과: `npm run agent:audit:api-boundary`
- 통과: `npm run agent:audit:web-boundary`
- 통과: `npm run agent:audit:ui`
- 통과: `docker compose -f docker-compose.dev.yml exec -T web npm run build`
- 참고: host `npm run web:build`는 `vite: not found`로 실패해 컨테이너에서 검증했다.

## 위험과 대응
- 위험: spectrum 탭 전환 시 추가 fetch가 발생한다.
- 대응: 초기 heatmap/trajectory 표시를 우선 빠르게 하고, spectrum 탭에서는 기존 loading 상태를 사용한다.
- 위험: heatmap x-bin 축소로 0.5nm 단위 전체 표시가 1nm 안팎 대표값 표시로 바뀔 수 있다.
- 대응: wavelength 클릭 후 trajectory는 가장 가까운 실제 wavelength 컬럼으로 조회한다.

## 진행 기록
- 2026-06-24: OES detail 초기 응답에서 불필요한 spectrum/heatmap 계산을 분리하는 방향으로 계획을 작성했다.
- 2026-06-24: `includeOesHeatmap`, `includeOesSpectrum` 옵션과 frontend lazy 요청 경로를 추가했다.
- 2026-06-24: `includeTraceDetails`, `includeOesDetails` 옵션으로 detail 대상이 아닌 raw 상세 계산을 건너뛰도록 했다.
- 2026-06-24: `api.pm_comparison` 테스트, backend/frontend/UI audit, web container build가 통과했다.
- 2026-06-25: 실제 OES 규모에 맞춰 mock raw와 step heatmap x-bin을 확대하고, 선택 step Parquet filter와 NumPy heatmap 계산 최적화를 추가했다.
- 2026-06-25: raw mock 재생성 후 `35,902,694 points -> 1200 x 100 matrix`를 확인했다. Heatmap service는 2.4~2.5초, trajectory-only는 0.818초로 측정됐다.
