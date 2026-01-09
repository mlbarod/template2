# Account Affiliation Logic / 계정 소속 로직

> KR: 이 문서는 현재 코드베이스 기준으로 user_sdwt_prod 소속/권한/승인/재확인/메일함 접근/프론트 UI 흐름을 **전체적으로** 설명합니다.  
> EN: This document **fully** explains user_sdwt_prod affiliation/access/approval/reconfirm/mailbox/UI flows based on the current codebase.

## 0. 범위 / Scope
- KR: account 도메인뿐 아니라 auth(OIDC), emails, assistant, 프론트 UI까지 포함합니다.
- EN: Covers the account domain plus auth (OIDC), emails, assistant, and frontend UI.

## 1. 빠른 지도 / Quick Map

### 1.1 핵심 모듈 / Core Modules
- KR: `apps/api/api/account/models.py` (소속/권한/변경 이력 모델)
- EN: `apps/api/api/account/models.py` (affiliation/access/change models)
- KR: `apps/api/api/account/selectors.py` (읽기 전용 조회 로직)
- EN: `apps/api/api/account/selectors.py` (read-only query logic)
- KR: `apps/api/api/account/services/*` (쓰기/비즈니스 로직)
- EN: `apps/api/api/account/services/*` (write/business logic)
- KR: `apps/api/api/account/views.py` (API 엔드포인트)
- EN: `apps/api/api/account/views.py` (API endpoints)
- KR: `apps/api/api/auth/services/oidc.py` (OIDC 클레임 매핑, 최초 로그인 처리)
- EN: `apps/api/api/auth/services/oidc.py` (OIDC claim mapping, first-login handling)
- KR: `apps/api/api/emails/selectors.py`, `apps/api/api/emails/services/mailbox.py` (메일함 멤버/요약)
- EN: `apps/api/api/emails/selectors.py`, `apps/api/api/emails/services/mailbox.py` (mailbox members/summary)
- KR: `apps/web/src/features/auth/components/*` (온보딩/재확인 UI)
- EN: `apps/web/src/features/auth/components/*` (onboarding/reconfirm UI)
- KR: `apps/web/src/features/account/*` (계정/멤버/권한 화면)
- EN: `apps/web/src/features/account/*` (account/members/access UI)
- KR: `apps/web/src/lib/profileImage.js` (avatarid 기반 아바타 URL)
- EN: `apps/web/src/lib/profileImage.js` (avatarid-based avatar URL)

### 1.2 주요 API 엔드포인트 / Key API Endpoints
| Method | Path | KR | EN |
| --- | --- | --- | --- |
| GET | `/api/v1/account/affiliation` | 소속 개요 + 소속 옵션 | Affiliation overview + options |
| POST | `/api/v1/account/affiliation` | 소속 변경 요청 | Request affiliation change |
| GET | `/api/v1/account/affiliation/requests` | 소속 변경 요청 목록 | List affiliation change requests |
| POST | `/api/v1/account/affiliation/approve` | 승인/거절 | Approve/Reject a change |
| GET | `/api/v1/account/affiliation/reconfirm` | 재확인 상태 조회 | Reconfirm status |
| POST | `/api/v1/account/affiliation/reconfirm` | 재확인 응답 | Reconfirm response |
| POST | `/api/v1/account/access/grants` | 접근 권한 부여/회수 | Grant/Revoke access |
| GET | `/api/v1/account/access/manageable` | 관리 가능 그룹/멤버 | Manageable groups + members |
| GET | `/api/v1/account/overview` | 계정 개요(통합) | Account overview (combined) |
| GET | `/api/v1/account/line-sdwt-options` | line/user_sdwt_prod 옵션 | Line/user_sdwt_prod options |
| POST | `/api/v1/account/external-affiliations/sync` | 외부 예측 소속 동기화 | External snapshot sync |
| GET | `/api/v1/auth/me` | 로그인 사용자 정보(소속 상태 포함) | Auth me (affiliation state) |

## 2. 용어 / Glossary
- KR: **user_sdwt_prod** = 소속 그룹 식별자(권한/메일함/RAG 기준 값)
- EN: **user_sdwt_prod** = affiliation group identifier (used for access/mailbox/RAG)
- KR: **knox_id** = 사용자 로그인 식별자(OIDC `loginid`)
- EN: **knox_id** = login identifier (OIDC `loginid`)
- KR: **avatarid** = 사용자 아바타 식별자(OIDC `userid`)
- EN: **avatarid** = avatar identifier (OIDC `userid`)
- KR: **Affiliation Option** = `(department, line, user_sdwt_prod)` 조합(사용자 선택용)
- EN: **Affiliation Option** = `(department, line, user_sdwt_prod)` selection option

## 3. 데이터 모델 / Data Model

### 3.1 User (account User)
- KR: `user_sdwt_prod` = 현재 소속
- EN: `user_sdwt_prod` = current affiliation
- KR: `department`, `line` = 현재 조직 정보
- EN: `department`, `line` = current org info
- KR: `requires_affiliation_reconfirm` = 외부 예측 변경으로 재확인 필요 여부
- EN: `requires_affiliation_reconfirm` = needs reconfirm due to external prediction change
- KR: `affiliation_confirmed_at` = 소속 확정 시각
- EN: `affiliation_confirmed_at` = timestamp when affiliation confirmed

### 3.2 Affiliation (옵션 테이블)
- KR: `(department, line, user_sdwt_prod)` 조합을 제공
- EN: Provides `(department, line, user_sdwt_prod)` options
- KR: `user_sdwt_prod`는 유니크 제약
- EN: `user_sdwt_prod` has a unique constraint

### 3.3 UserSdwtProdAccess (접근 권한)
- KR: `user` + `user_sdwt_prod` 조합에 대한 역할 저장
- EN: Stores role for a `(user, user_sdwt_prod)` pair
- KR: `role` = `viewer | member | manager`
- EN: `role` = `viewer | member | manager`
- KR: `granted_by` = 권한 부여자
- EN: `granted_by` = grantor

### 3.4 UserSdwtProdChange (소속 변경 이력)
- KR: `from_user_sdwt_prod` → `to_user_sdwt_prod` 변경 기록
- EN: Change record from `from_user_sdwt_prod` to `to_user_sdwt_prod`
- KR: `status` = `PENDING | APPROVED | REJECTED | SUPERSEDED`
- EN: `status` = `PENDING | APPROVED | REJECTED | SUPERSEDED`
- KR: `effective_from` = 적용 기준 시각
- EN: `effective_from` = effective time

### 3.5 ExternalAffiliationSnapshot (외부 예측)
- KR: `knox_id` 기준으로 `predicted_user_sdwt_prod` 저장
- EN: Stores `predicted_user_sdwt_prod` by `knox_id`
- KR: 변경 시 재확인 플래그를 세우는 트리거로 사용
- EN: Used to trigger reconfirm when prediction changes

## 4. 역할 모델 / Role Model
| Role | KR (권한 요약) | EN (Summary) |
| --- | --- | --- |
| viewer | 조회만 가능 | Read-only |
| member | 승인 가능 | Can approve affiliation changes |
| manager | 승인 + 권한 관리 | Can approve + manage grants |

- KR: 역할 우선순위는 `viewer < member < manager` 입니다.
- EN: Role order is `viewer < member < manager`.
- KR: `ensure_self_access`는 현재 소속에 대해 `viewer` 요청을 `member`로 승급합니다.
- EN: `ensure_self_access` upgrades `viewer` to `member` for current affiliation.
- KR: superuser/staff는 승인에서 항상 관리자급으로 취급됩니다.
- EN: superuser/staff are always treated as privileged approvers.

## 5. 상태 모델 / Status Model
| Status | KR 의미 | EN Meaning |
| --- | --- | --- |
| PENDING | 승인 대기 | Waiting for approval |
| APPROVED | 승인/적용 완료 | Approved & applied |
| REJECTED | 거절 | Rejected |
| SUPERSEDED | 대체됨(이전 요청 폐기) | Superseded by a newer request |

- KR: `REJECTED` 필터는 `SUPERSEDED`도 포함하도록 동작합니다.
- EN: `REJECTED` filter also includes `SUPERSEDED` items.

## 6. 조회 로직 (Selectors) / Read Logic

### 6.1 접근 가능한 그룹 집합
**Function**: `get_accessible_user_sdwt_prods_for_user`
- KR: 인증 사용자라면 본인 소속 + 접근 권한 행을 합쳐 반환합니다.
- EN: Returns current affiliation + access rows for authenticated users.
- KR: 소속이 없으면 “대기 중 변경(to_user_sdwt_prod)”도 포함합니다.
- EN: If no affiliation, includes pending change `to_user_sdwt_prod`.
- KR: superuser는 시스템에 존재하는 모든 값(옵션/권한/유저)을 합쳐 반환합니다.
- EN: superusers get the union of all known values (options/access/users).

### 6.2 관리 가능한 그룹
**Function**: `list_manageable_user_sdwt_prod_values`
- KR: role이 `manager`인 그룹만 반환합니다.
- EN: Returns only groups where role is `manager`.

### 6.3 승인 가능한 그룹
**Function**: `list_approvable_user_sdwt_prod_values`
- KR: role이 `member` 또는 `manager`인 그룹 반환
- EN: Returns groups where role is `member` or `manager`.

### 6.4 승인자 존재 여부
**Function**: `has_approver_for_user_sdwt_prod`
- KR: 특정 그룹에 `member/manager` 접근 권한이 존재하는지 확인
- EN: Checks if any `member/manager` exists for the group

### 6.5 변경 요청 목록 필터
**Function**: `list_affiliation_change_requests`
- KR: `allowed_user_sdwt_prods`, `status`, `search`, `user_sdwt_prod`로 필터
- EN: Filters by `allowed_user_sdwt_prods`, `status`, `search`, `user_sdwt_prod`
- KR: 검색은 username/email/sabun/knox_id/givenname/surname에 대해 수행
- EN: Search runs across username/email/sabun/knox_id/givenname/surname

## 7. 쓰기 로직 (Services) / Write Logic

### 7.1 ensure_self_access
**목적 / Purpose**: 현재 소속에 대한 접근 권한 행 보장
- KR: 현재 소속이 없으면 아무 것도 하지 않습니다.
- EN: No-op if current affiliation is missing.
- KR: 존재하지 않으면 생성, 존재하면 상향(upgrade)만 수행합니다.
- EN: Creates if missing, only upgrades if needed.

### 7.2 grant_or_revoke_access
**목적 / Purpose**: 권한 부여/회수
- KR: 관리 권한 검증 후 grant/revoke 수행
- EN: Performs grant/revoke after manager check
- KR: revoke 시 현재 소속(user_sdwt_prod) 권한은 제거할 수 없습니다.
- EN: Cannot revoke access for a user’s current affiliation.
- KR: revoke로 마지막 manager가 사라지면 거부합니다.
- EN: Revoke fails if it would remove the last manager.

### 7.3 request_affiliation_change
**목적 / Purpose**: 소속 변경 요청 생성
- KR: 기존 PENDING이 있으면 새 요청을 만들고 이전 요청은 SUPERSEDED 처리
- EN: If a PENDING exists, new request supersedes the old one
- KR: 자동 적용 조건 = (예측값 일치) 또는 (승인자 없음)
- EN: Auto-apply if (prediction matches) OR (no approver exists)
- KR: 자동 적용이면 `effective_from`을 현재 시각으로 덮어씁니다.
- EN: Auto-apply overwrites `effective_from` with now.

### 7.4 approve_affiliation_change / reject_affiliation_change
- KR: 승인자는 member/manager 또는 privileged 사용자
- EN: Approver must be member/manager or privileged
- KR: 승인 시 사용자 소속을 갱신하고 change를 APPROVED로 바꿉니다.
- EN: Approval updates user affiliation and sets change to APPROVED.
- KR: 거절 시 REJECTED로 변경하고 거절 사유를 저장합니다.
- EN: Rejection sets REJECTED and stores reason.

### 7.5 submit_affiliation_reconfirm_response
- KR: 재확인 플래그가 없으면 409 반환
- EN: Returns 409 if reconfirm is not required.
- KR: accepted=false면 기존 유지(플래그 해제)
- EN: accepted=false keeps current affiliation and clears the flag.
- KR: accepted=true면 선택한 user_sdwt_prod로 변경 요청을 생성
- EN: accepted=true creates a change request for selected user_sdwt_prod.

### 7.6 auto_approve_affiliation_from_snapshot
- KR: 신규 사용자 최초 로그인 시 예측 소속으로 자동 적용 시도
- EN: Attempts auto-apply to predicted affiliation on first login.

### 7.7 sync_external_affiliations
- KR: 외부 예측 변경 감지 시 사용자에 재확인 플래그 설정
- EN: Sets reconfirm flag if external prediction changes.

## 8. API 상세 흐름 / API Detailed Flows

### 8.1 GET `/api/v1/account/affiliation`
- KR: 현재 소속 정보 + 접근 목록 + 소속 옵션 반환
- EN: Returns current affiliation + access list + affiliation options

**예시 응답 / Example Response**
```json
{
  "currentUserSdwtProd": "G-A",
  "currentDepartment": "Dept",
  "currentLine": "Line",
  "timezone": "Asia/Seoul",
  "accessibleUserSdwtProds": [
    {
      "userSdwtProd": "G-A",
      "role": "member",
      "source": "self",
      "grantedBy": null,
      "grantedAt": null
    }
  ],
  "manageableUserSdwtProds": ["G-A"],
  "affiliationOptions": [
    {"department": "Dept", "line": "Line", "user_sdwt_prod": "G-A"}
  ]
}
```

### 8.2 POST `/api/v1/account/affiliation`
- KR: 소속 변경 요청(자동 적용 또는 PENDING)
- EN: Create affiliation change (auto-applied or pending)
- KR: 입력 키는 `user_sdwt_prod` 또는 `userSdwtProd` 지원
- EN: Supports `user_sdwt_prod` or `userSdwtProd`

**예시 요청 / Example Request**
```json
{
  "user_sdwt_prod": "G-B",
  "effective_from": "2025-12-28T10:00:00+09:00"
}
```

**예시 응답 (대기) / Example Response (Pending)**
```json
{
  "status": "pending",
  "changeId": 101,
  "userSdwtProd": "G-B",
  "effectiveFrom": "2025-12-28T01:00:00Z"
}
```

**예시 응답 (자동 적용) / Example Response (Auto-applied)**
```json
{
  "status": "applied",
  "changeId": 102,
  "userId": 1,
  "userSdwtProd": "G-B",
  "effectiveFrom": "2025-12-28T01:05:00Z"
}
```

### 8.3 GET `/api/v1/account/affiliation/requests`
- KR: 승인 대상 요청 목록 반환
- EN: Returns approvable change requests

**예시 응답 / Example Response**
```json
{
  "results": [
    {
      "id": 201,
      "status": "PENDING",
      "department": "Dept",
      "line": "Line",
      "fromUserSdwtProd": "G-A",
      "toUserSdwtProd": "G-B",
      "effectiveFrom": "2025-12-28T01:00:00Z",
      "approvedAt": null,
      "requestedAt": "2025-12-20T02:00:00Z",
      "approvedBy": null,
      "requestedBy": {"id": 1, "username": "홍길동"},
      "rejectionReason": null,
      "role": "member",
      "user": {
        "id": 1,
        "username": "홍길동",
        "email": "hong@example.com",
        "sabun": "S123",
        "knoxId": "KNOX-1",
        "department": "Dept",
        "line": "Line",
        "userSdwtProd": "G-A"
      }
    }
  ],
  "page": 1,
  "pageSize": 20,
  "total": 1,
  "totalPages": 1
}
```

### 8.4 POST `/api/v1/account/affiliation/approve`
- KR: 승인/거절 처리
- EN: Approve or reject a change

**예시 요청 (승인) / Example Request (Approve)**
```json
{"changeId": 201, "decision": "approve"}
```

**예시 응답 (승인) / Example Response (Approve)**
```json
{
  "status": "approved",
  "changeId": 201,
  "userId": 1,
  "userSdwtProd": "G-B",
  "effectiveFrom": "2025-12-28T01:00:00Z"
}
```

**예시 요청 (거절) / Example Request (Reject)**
```json
{"changeId": 201, "decision": "reject", "rejectionReason": "권한 없음"}
```

**예시 응답 (거절) / Example Response (Reject)**
```json
{"status": "rejected", "changeId": 201}
```

### 8.5 GET/POST `/api/v1/account/affiliation/reconfirm`
- KR: 외부 예측 변경 시 사용자가 재확인
- EN: User reconfirmation when external prediction changed

**예시 응답 (GET) / Example Response (GET)**
```json
{
  "requiresReconfirm": true,
  "predictedUserSdwtProd": "G-NEW",
  "currentUserSdwtProd": "G-OLD"
}
```

**예시 요청 (POST, 기존 유지) / Example Request (Keep)**
```json
{"accepted": false}
```

**예시 요청 (POST, 변경 적용) / Example Request (Apply)**
```json
{"accepted": true, "user_sdwt_prod": "G-NEW"}
```

### 8.6 POST `/api/v1/account/access/grants`
- KR: 특정 그룹에 role 부여/회수
- EN: Grant/revoke role for a target group

**예시 요청 / Example Request**
```json
{"user_sdwt_prod": "G-A", "userId": 55, "action": "grant", "role": "manager"}
```

**예시 응답 / Example Response**
```json
{
  "userId": 55,
  "username": "kim",
  "name": "kim",
  "knoxId": "KNOX-55",
  "userSdwtProd": "G-A",
  "role": "manager",
  "grantedBy": 1,
  "grantedAt": "2025-12-20T02:00:00Z"
}
```

### 8.7 GET `/api/v1/account/access/manageable`
- KR: 관리 가능한 그룹과 멤버 목록
- EN: Returns manageable groups and members

### 8.8 GET `/api/v1/account/overview`
- KR: 소속/이력/메일함 요약을 묶어 반환
- EN: Returns a combined overview (affiliation/history/mailbox)

### 8.9 GET `/api/v1/account/line-sdwt-options`
- KR: line별 선택 가능한 user_sdwt_prod 목록 반환
- EN: Returns selectable user_sdwt_prod values per line

### 8.10 POST `/api/v1/account/external-affiliations/sync`
- KR: 외부 예측 소속 스냅샷 동기화
- EN: Sync external prediction snapshots

**예시 요청 / Example Request**
```json
{
  "records": [
    {
      "knox_id": "KNOX-1",
      "user_sdwt_prod": "G-NEW",
      "source_updated_at": "2025-12-01T00:00:00Z"
    }
  ]
}
```

**예시 응답 / Example Response**
```json
{"created": 1, "updated": 0, "unchanged": 0, "flagged": 1}
```

### 8.11 GET `/api/v1/auth/me`
- KR: 사용자 정보 + pending 상태 제공
- EN: Returns user info + pending affiliation status

**예시 응답 / Example Response**
```json
{
  "id": 1,
  "usr_id": "KNOX-1",
  "avatarid": "U-12345",
  "username": "홍길동",
  "email": "hong@example.com",
  "user_sdwt_prod": "G-A",
  "pending_user_sdwt_prod": null,
  "has_pending_affiliation": false
}
```

## 9. 프론트엔드 흐름 / Frontend Flows

### 9.1 온보딩 다이얼로그
- KR: `user_sdwt_prod`가 없고 pending이 없으면 소속 선택을 강제합니다.
- EN: If `user_sdwt_prod` is empty and no pending change, onboarding is required.
- KR: `/api/v1/account/affiliation`에서 옵션을 가져옵니다.
- EN: Options are fetched from `/api/v1/account/affiliation`.

### 9.2 재확인 다이얼로그
- KR: `requiresReconfirm=true`이고 pending이 없으면 재확인 다이얼로그 표시
- EN: Shows reconfirm dialog when `requiresReconfirm=true` and no pending change
- KR: 사용자는 다이얼로그를 닫고 나중에 진행할 수 있습니다.
- EN: Users can dismiss the dialog and handle it later.

### 9.3 멤버/요청 화면
- KR: `affiliation/requests`의 `role`로 승인 버튼 활성화 여부 결정
- EN: Uses `role` from `affiliation/requests` to enable/disable approvals

### 9.4 계정 개요 화면
- KR: `/account/overview`를 통해 소속/이력/메일함 접근 현황을 한 번에 표시
- EN: Uses `/account/overview` to show affiliation/history/mailbox in one place

## 10. 이메일/어시스턴트 연동 / Email & Assistant Integration
- KR: 메일함 멤버 조회는 account 접근 권한과 사용자 소속을 병합해 반환합니다.
- EN: Mailbox members combine access rows and affiliated users.
- KR: assistant 권한 그룹은 `get_accessible_user_sdwt_prods_for_user`를 사용합니다.
- EN: Assistant permission groups come from `get_accessible_user_sdwt_prods_for_user`.

## 11. 대표 시나리오 / Example Scenarios

### 시나리오 A: 신규 사용자 자동 적용
- KR: 사용자 생성 → 외부 예측 존재 → 자동 승인/적용
- EN: User created → external prediction exists → auto approve/apply

### 시나리오 B: 승인자 존재로 대기
- KR: 예측 불일치 + 승인자 존재 → PENDING 생성 → 승인자 승인
- EN: Prediction mismatch + approver exists → PENDING → approved by approver

### 시나리오 C: 재확인 플래그 발생
- KR: 외부 예측 변경 → requires_affiliation_reconfirm=true → 사용자가 재확인 응답
- EN: Prediction changes → reconfirm flag set → user responds

### 시나리오 D: 권한 위임
- KR: manager가 `/access/grants`로 member/manager 권한 부여
- EN: Manager grants member/manager role via `/access/grants`

## 12. 에러/엣지 케이스 / Errors & Edge Cases
- KR: 현재 소속의 권한은 revoke로 제거할 수 없습니다.
- EN: Cannot revoke access for a user’s current affiliation.
- KR: 마지막 manager를 제거하려는 revoke는 거부됩니다.
- EN: Revoke fails if it removes the last manager.
- KR: 기존 PENDING이 있으면 새 요청이 기존 요청을 SUPERSEDED 처리합니다.
- EN: A new request supersedes an existing PENDING.
- KR: 자동 적용 시 effective_from은 현재 시각으로 덮어씁니다.
- EN: Auto-apply overwrites effective_from with now.

