# ExecPlan: PM SPIDER 성능 개선

## 목표
- PM SPIDER 드롭다운과 조회가 선택한 PM 날짜 기준으로 파일 탐색 범위를 좁히도록 수정한다.
- 기존 `/api/v1/pm_spider/meta`, `/api/v1/pm_spider/compare` 계약을 깨지 않고 조회 지연 원인을 줄인다.

## 현재 상태
- 프론트는 `form` 전체를 `/meta` query key로 사용해 선택 변경마다 metadata를 다시 요청한다.
- 백엔드 metadata 필터는 `pmTimestamp`를 raw `dt` partition으로 변환하지 않는다.
- `/compare` raw 조회는 `dtValues`가 있을 때만 날짜로 좁혀지고, 기본 payload에는 `dtValues`가 없다.
- score/raw/OES parquet는 파일 시스템 glob과 pandas read 기반으로 처리된다.

## 범위
- 수정: `apps/web/src/features/pm-spider/**`, `apps/api/api/pm_comparison/**`
- 수정: PM SPIDER 회귀 테스트
- 제외: DB migration, auth/permission, 신규 데이터 적재 파이프라인

## 설계
- `pmTimestamp`를 raw metadata 필터의 `dt`로 매핑한다.
- compare selection에 `dtValues`가 없으면 `pmTimestamp`에서 raw 조회 날짜 후보를 생성한다.
- score 기반 ref cycle 날짜가 확인되면 raw 조회 날짜 후보에 반영해 불필요한 `dt=*` 탐색을 피한다.
- 프론트 payload에 `dtValues: [pmTimestamp]`를 포함해 기존 serializer 필드를 활용한다.
- 초기 category 조회는 `includeDetails=false`로 score summary만 받고, 상세 그래프는 기존 detail query에서 `includeDetails=true`로 가져온다.
- raw metadata는 프로세스 내 directory index cache로 재사용한다.
- public API는 하위 호환을 유지한다.

## 실행 단계
- [x] `pmTimestamp` 기반 metadata 필터를 추가한다.
- [x] compare raw 조회 날짜 후보를 current/ref cycle 기준으로 좁힌다.
- [x] 프론트 payload에 `dtValues`를 포함한다.
- [x] 초기 summary와 상세 조회를 `includeDetails`로 분리한다.
- [x] 회귀 테스트를 추가/수정한다.
- [ ] Docker Compose `api` 컨테이너 기준 테스트를 실행한다.

## 검증
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py test api.pm_comparison`
- 프론트 변경은 import/빌드 영향이 작으므로 필요 시 `npm run agent:audit:web-boundary`

## 위험과 대응
- 위험: raw layout의 날짜 문자열이 `YYYY-MM-DD`와 `YYYYMMDD` 양쪽으로 존재할 수 있다.
- 대응: 현재 선택 문자열과 정규화된 날짜 문자열을 후보로 함께 사용한다.
- 위험: ref cycle 날짜까지 raw 조회에 포함하면 파일 수가 늘 수 있다.
- 대응: score에서 실제 선택된 ref 날짜만 후보로 사용하고 기존 `PM_COMPARISON_MAX_FILES` 제한을 유지한다.

## 진행 기록
- 2026-06-19: PM SPIDER metadata/raw 조회가 `pmTimestamp`를 partition 필터로 쓰지 않는 병목을 확인하고 계획을 작성했다.
- 2026-06-19: `pmTimestamp` 날짜 후보 매핑, raw metadata index cache, raw 조회 `dtValues` 보강, `includeDetails` 기반 summary/detail 분리를 구현했다.
