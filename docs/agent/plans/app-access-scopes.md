# ExecPlan: 앱 단위 접근 scope 도입

## 목표
- 포털 내부 앱별 권한을 후속 단계에서 연결할 수 있도록 `AccessScope` 앱 레코드를 기본 데이터로 등록한다.

## 현재 상태
- `account.AccessScope`는 `portal`, `app`, `feature` 유형을 이미 지원한다.
- 기본 데이터 migration에는 `portal` scope만 등록되어 있다.
- 프론트엔드 앱 접근 카탈로그에는 포털 화면과 내부 앱의 안정적인 앱 키가 정의되어 있다.

## 범위
- 실제 내부 앱 12개의 app scope를 데이터 migration으로 추가한다.
- seed 결과를 account 테스트에서 검증한다.
- 앱별 사용자 권한 부여, 접근 요청 UI, 프론트엔드 route gate, 백엔드 API 차단은 수정하지 않는다.

## 설계
- 앱 키는 기존 앱 접근 카탈로그의 `appId`와 일치시킨다.
- `home`, `settings`는 독립 앱이 아니라 포털 공통 화면이므로 기존 `portal` scope로 관리한다.
- 각 앱 scope는 `scope_type=app`, 활성, 신청 가능, 기본 역할 `viewer`로 생성한다.
- migration은 기존 동일 키 레코드를 덮어쓰지 않고 누락된 scope만 생성한다.
- 기존 동일 키가 app 유형이 아니면 migration을 중단하며, 역방향에서는 운영 권한 데이터를 삭제하지 않는다.

## 실행 단계
- [x] 앱 scope 데이터 migration 추가
- [x] 기본 scope 구성 테스트 추가
- [x] migration 및 account 테스트 검증

## 검증
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py makemigrations --check`
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py test api.account.tests.AccountEndpointTests.test_default_app_access_scopes_are_seeded`
- `npm run agent:audit:api-boundary`
- 기대 결과: 추가 migration 필요 없음, 앱 scope 12개와 속성 검증 통과, 경계 감사 통과

## 위험과 대응
- 위험: 앱 카탈로그와 migration 목록이 향후 달라질 수 있다.
- 대응: 현재 안정적인 `appId`를 scope key 계약으로 사용하고 앱 추가 시 새 데이터 migration으로 확장한다.
- 위험: scope만 존재하고 실제 접근이 차단된 것으로 오해할 수 있다.
- 대응: 이번 범위에서 enforcement를 명시적으로 제외하고 결과에 남긴다.

## 진행 기록
- 2026-07-10: 앱 단위 scope 등록 범위와 기본값을 확정했다.
- 2026-07-10: 앱 scope seed를 권한 migration에 포함하고 migration 정합성, 집중 테스트, 백엔드 경계 감사를 통과했다.
- 2026-07-10: 코드 리뷰 결과를 반영해 기존 scope 유형 충돌을 검증하고 역방향을 no-op으로 변경했다.
