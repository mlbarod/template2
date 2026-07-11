# Account 모듈

Account는 이 앱의 권한 기준이 되는 소속과 접근 권한을 관리합니다.

## 기능 요약

- 현재 사용자 소속 조회
- 소속 변경 요청/승인/거절
- 외부 예측 소속 동기화와 재확인
- `user_sdwt_prod` 접근 권한 부여/회수
- Portal·앱 접근 권한 통합 매트릭스 관리
- 소속별 멤버 조회
- 사용자 검색 pool 제공

## 왜 중요한가

`user_sdwt_prod`는 단순한 사용자 정보가 아니라 접근 권한의 기준입니다.

- Emails는 접근 가능한 소속 메일함만 보여줍니다.
- Assistant는 접근 가능한 소속만 RAG 검색 범위에 넣습니다.
- Drone은 대상 소속을 기준으로 알림 수신자를 정합니다.

## 핵심 데이터

| 모델 | 의미 |
| --- | --- |
| `User` | 사용자 기본 정보와 현재 소속 |
| `Affiliation` | 선택 가능한 부서/라인/user_sdwt_prod 조합 |
| `UserSdwtProdAccess` | 소속 접근 권한 |
| `UserSdwtProdChange` | 소속 변경 요청 이력 |
| `ExternalAffiliationSnapshot` | 외부 시스템이 예측한 소속 |
| `AccessScope` | Portal·앱·기능별 접근 권한 범위 |
| `UserAccess` | 사용자별 scope 승인 상태와 Portal 역할 |

## 소속 접근 role

| Role | 의미 |
| --- | --- |
| `viewer` | 조회 가능 |
| `member` | 조회 + 소속 변경 승인 가능 |
| `manager` | 조회 + 승인 + 권한 관리 가능 |

staff/superuser는 대부분의 소속 제한을 우회합니다.

## Portal·앱 접근 계층

- Portal 접근이 허용되어야 앱 접근 판정도 최종 허용될 수 있습니다.
- Portal이 차단되면 개별 앱이 수동 또는 자동 허용 상태여도 최종 앱 접근은 차단됩니다.
- 차단 전 앱 판정은 API의 `underlyingAccess`에 보존되므로 Portal 복구 후 기존 앱 설정이 다시 적용됩니다.
- Portal의 `viewer`, `member`, `manager`, `admin` 역할은 접근 분류값이며 권한 관리 기능을 부여하지 않습니다.
- 권한 관리 기능은 별도 Django permission인 `account.manage_access`와 `Access Managers` 그룹으로만 부여합니다.
- superuser 우회 외에는 Portal 역할과 권한 관리 capability 모두 Portal 차단 자체를 우회하지 않습니다.

## 소속 변경 흐름

1. 사용자가 새 `user_sdwt_prod`를 제출합니다.
2. 서버가 `Affiliation`에 존재하는 값인지 확인합니다.
3. 기존 대기 요청이 있으면 이전 요청을 `SUPERSEDED`로 바꿉니다.
4. 예측 소속과 같거나 승인자가 없으면 자동 적용합니다.
5. 승인이 필요하면 `PENDING` 요청으로 저장합니다.
6. `member` 또는 `manager`가 승인하면 사용자 소속이 갱신됩니다.

## 외부 예측 소속 재확인

1. Airflow가 외부 예측 소속을 동기화합니다.
2. 예측값이 현재 소속과 달라지면 재확인 플래그가 켜집니다.
3. 사용자는 예측값을 수락하거나 다른 소속을 선택합니다.
4. 다른 소속을 선택하면 승인 대기로 갈 수 있습니다.

## 대표 시나리오

| 상황 | 결과 |
| --- | --- |
| 신규 사용자에게 유효한 예측 소속이 있음 | 자동 적용 가능 |
| 예측 소속이 없거나 유효하지 않음 | 온보딩에서 직접 선택 |
| 예측값과 같은 소속 선택 | 자동 적용 가능 |
| 승인자가 있고 예측값과 다른 소속 선택 | 승인 대기 |
| 승인 대기 중 재요청 | 이전 요청은 `SUPERSEDED` |
| 마지막 manager 회수 시도 | 거부 |

## 화면/API/데이터 추적

| 구간 | 위치 |
| --- | --- |
| 화면 | `/settings/account`, `/settings/members`, `/settings/permissions` |
| Frontend | `apps/web/src/features/account`, `apps/web/src/features/auth` |
| Backend API | `/api/v1/account/**`, `/api/v1/auth/me` |
| 데이터 | `User`, `Affiliation`, `UserCurrentAffiliation`, `UserSdwtProdAccess`, `UserSdwtProdChange`, `ExternalAffiliationSnapshot` |
| 외부/배치 | Airflow `external-affiliations/sync` |

## 운영 포인트

- 소속이 예상과 다르면 `ExternalAffiliationSnapshot`과 `UserCurrentAffiliation`을 함께 확인합니다.
- 소속 권한 문제는 `UserSdwtProdAccess` role을, Portal·앱 권한 문제는 `UserAccess`, `AccessPolicyRule`, Portal 최종 판정을 함께 확인합니다.
- 권한 관리 화면 접근 문제는 Portal 역할이 아니라 `account.manage_access` permission과 `Access Managers` 그룹을 확인합니다.
- 외부 동기화 실패는 Airflow Bearer token과 `docs/configuration.md`의 auth/env 설정을 확인합니다.

## 관련 API

- `docs/api/account.md`

## 관련 코드

- `apps/api/api/account/views.py`
- `apps/api/api/account/models.py`
- `apps/api/api/account/selectors.py`
- `apps/api/api/account/serializers.py`
- `apps/api/api/account/services/access.py`
- `apps/api/api/account/services/affiliation_requests.py`
- `apps/api/api/account/services/affiliations.py`
- `apps/api/api/account/services/external_sync.py`
- `apps/api/api/account/services/overview.py`
- `apps/api/api/account/services/users.py`
- `apps/web/src/features/account`
- `apps/web/src/features/auth`
