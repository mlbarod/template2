# ExecPlan: access-stats 수동 외부 API 동기화

## 목표
- access-stats 화면 조회 중 외부 API를 직접 호출하지 않는다.
- 슈퍼유저가 버튼으로 외부 API 데이터를 수동 동기화한다.
- 마지막 동기화 후 1시간 이내에는 재동기화하지 않는다.

## 현재 상태
- `get_app_access_stats_payload()`가 `_load_external_usage_rows()`를 통해 조회 중 외부 API를 호출한다.
- `ExternalAppAccessDailyStat`는 외부/수동 앱 일별 집계 저장에 이미 사용된다.
- 프론트 access-stats는 통계 조회 hook과 상단 KPI 액션 카드가 있다.

## 범위
- 수정: activity 모델/마이그레이션, service/view/url/test, access-stats API/hook/page
- 제외: 주기 scheduler, cron, 운영 배포 설정

## 설계
- `ExternalAppUsageSyncState` 모델로 마지막 동기화 상태를 저장한다.
- `sync_external_app_usage_stats()`는 외부 API를 호출해 최근 365일 row를 `source_type=external_api`로 upsert한다.
- 1시간 이내 재요청은 외부 API 호출 없이 skipped 응답을 반환한다.
- 통계 조회는 `ExternalAppAccessDailyStat` DB row만 사용한다.

## 실행 단계
- [x] 모델과 마이그레이션 추가
- [x] 외부 API 수동 동기화 service 추가
- [x] 통계 조회에서 외부 API 직접 호출 제거
- [x] 동기화 API endpoint 추가
- [x] 프론트 수동 동기화 버튼/API/mutation 추가
- [x] 테스트와 audit 실행

## 검증
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py test api.activity`
- `npm run web:lint`
- `npm run agent:audit:api-boundary`
- `npm run agent:audit:web-boundary`
- `npm run agent:audit:ui`

## 위험과 대응
- 위험: 외부 API 실패 시 기존 저장 데이터가 사라짐
- 대응: 실패 시 upsert를 수행하지 않고 기존 DB 데이터를 유지한다.
- 위험: 1시간 제한이 브라우저 캐시로 우회됨
- 대응: 서버 DB 상태 기준으로 제한한다.

## 진행 기록
- 2026-07-02: 수동 동기화 + 1시간 제한 구조로 확정.
- 2026-07-02: 구현 완료. 통계 조회 경로에서 외부 API 호출 제거, 수동 동기화 endpoint/UI 추가, 검증 통과.
- 2026-07-02: 조회는 모든 인증 사용자에게 허용, 일반 사용자 동기화는 1시간 제한 적용, 슈퍼유저 동기화는 제한 우회로 조정.
