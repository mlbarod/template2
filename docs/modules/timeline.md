# Timeline 모듈

Timeline은 설비 타임라인 화면에 필요한 기준 정보와 로그를 조회합니다.

## 기능 요약

- 라인 목록 조회
- 라인별 SDWT 조회
- 공정 그룹 조회
- 설비 목록/상세 조회
- 설비별 로그 조회

## 데이터 소스

대부분 timeline 전용 PostgreSQL DB를 조회합니다. 일부 Drone/Jira 관련 로그는 기본 DB를 함께 사용할 수 있습니다.

## 조회 흐름

1. 요청 query를 정리합니다.
2. `lineId`, `sdwtId`, `prcGroup` 등 식별자를 대문자로 정규화합니다.
3. 필수 query가 없으면 400을 반환합니다.
4. DB에서 목록 또는 로그를 조회합니다.
5. 프론트가 사용하기 쉬운 형태로 반환합니다.

## 관련 API

- `docs/api/timeline.md`

## 관련 코드

- `apps/api/api/timeline/views.py`
- `apps/api/api/timeline/selectors.py`
- `apps/web/src/features/timeline`
