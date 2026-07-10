# ExecPlan: L3 Spider 미사용 설비 랭킹 제거

## 목표
- L3 Spider Daily Summary에서 프론트가 사용하지 않는 `equipmentRanking` 계산과 응답 필드를 제거한다.
- 날짜별 전체 Parquet 재읽기를 없애 초기 Summary 응답 시간을 줄인다.

## 현재 상태
- `get_daily_summary()`는 인덱스 기반 본문 집계 후 설비 랭킹을 위해 날짜의 모든 Parquet를 다시 읽는다.
- 저장소 내부 프론트는 `headline`, `matrix`, `runStats`만 사용한다.
- `equipmentRanking`은 백엔드 테스트 외 사용처가 없다.

## 범위
- 수정: `apps/api/api/l3_spider/services/__init__.py`, `apps/api/api/l3_spider/tests.py`.
- 제외: 프론트 UI, SQLite schema, migration, 캐시 구조, Parquet 생성 계약.

## 설계
- Daily Summary 응답에서 `equipmentRanking` 필드를 제거한다.
- 미사용 랭킹 함수와 호출부를 제거한다.
- 헤드라인, 매트릭스, 실행 통계 응답은 유지한다.
- API 응답 계약 변경이며 DB/env/auth 영향은 없다.

## 실행 단계
- [x] 미사용 랭킹 계산과 응답 필드 제거
- [x] Daily Summary 회귀 테스트 갱신
- [x] L3 Spider 테스트 및 백엔드 경계 검사
- [x] 콜드 경로 실행시간 재측정

## 검증
- `docker compose exec -T api python manage.py test api.l3_spider`
- `npm run agent:audit:api-boundary`
- API 컨테이너에서 캐시를 비우고 `get_daily_summary()` 실행시간 측정

## 위험과 대응
- 위험: 저장소 외부 소비자가 `equipmentRanking`을 참조할 수 있다.
- 대응: 사용자의 미사용 확인을 계약 제거 승인으로 간주하고 저장소 내부 사용처를 재검색한다.

## 진행 기록
- 2026-07-10: 저장소 내부 미사용 확인 및 제거 작업 시작.
- 2026-07-10: L3 Spider 테스트 20개 및 Python 3.12 백엔드 경계 검사 통과.
- 2026-07-10: 로컬 콜드 호출이 날짜별 0.0153~0.0749초로 단축되고 제거 필드가 응답에 없음을 확인.
- 2026-07-10: `main` 반영으로 원복된 서비스와 테스트 변경을 `y5`에 재적용.
