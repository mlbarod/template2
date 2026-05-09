# Account API

Account API는 사용자 소속, 접근 권한, 사용자 검색을 제공합니다.

## 호출자

- 브라우저 SPA
- Airflow 또는 외부 배치
- Emails/Assistant 등 내부 모듈

## 인증

- 일반 API: Django session 필요
- 외부 소속 동기화: Airflow Bearer token 필요

## Endpoint

| Method | Path | Auth | 설명 |
| --- | --- | --- | --- |
| GET | `/api/v1/account/overview` | Session | 계정 화면 통합 정보 |
| GET | `/api/v1/account/affiliation` | Session | 내 소속/접근 가능 소속/선택 옵션 |
| POST | `/api/v1/account/affiliation` | Session | 소속 변경 요청 |
| GET | `/api/v1/account/affiliation/requests` | Session | 소속 변경 요청 목록 |
| POST | `/api/v1/account/affiliation/approve` | Session | 소속 변경 승인/거절 |
| GET | `/api/v1/account/affiliation/members` | Session | 소속 멤버 목록 |
| GET/POST | `/api/v1/account/affiliation/reconfirm` | Session | 외부 예측 소속 재확인 |
| POST | `/api/v1/account/external-affiliations/sync` | Bearer token | 외부 예측 소속 동기화 |
| POST | `/api/v1/account/access/grants` | Session | 접근 권한 부여/회수 |
| GET | `/api/v1/account/access/manageable` | Session | 관리 가능한 소속과 멤버 |
| GET | `/api/v1/account/users` | Session | 사용자 검색 pool |
| GET | `/api/v1/account/line-sdwt-options` | Session | line/user_sdwt_prod 옵션 |

## 소속 변경 요청

```http
POST /api/v1/account/affiliation
Content-Type: application/json
```

```json
{
  "user_sdwt_prod": "G-A"
}
```

호환 키:

- `user_sdwt_prod`
- `userSdwtProd`

응답은 자동 적용 또는 승인 대기 상태를 반환합니다.

## 승인/거절

```json
{
  "changeId": 123,
  "decision": "approve"
}
```

거절:

```json
{
  "changeId": 123,
  "decision": "reject",
  "rejectionReason": "소속 정보 불일치"
}
```

## 권한 부여/회수

```json
{
  "user_sdwt_prod": "G-A",
  "userId": 55,
  "action": "grant",
  "role": "manager"
}
```

허용 role:

- `viewer`
- `member`
- `manager`

대상 사용자 키:

- `userId`
- `user_id`
- `knox_id`

## 사용자 검색

```http
GET /api/v1/account/users?search=kim&contactField=email
```

쿼리:

| Query | 설명 |
| --- | --- |
| `search` | 사용자 검색어 |
| `user_sdwt_prod`, `userSdwtProd` | 소속 필터 |
| `contactField` | `email` 또는 `knox_id` |
| `limit` | 숫자 또는 조건부 `all` |

## 외부 소속 동기화

```http
POST /api/v1/account/external-affiliations/sync
Authorization: Bearer <AIRFLOW_TRIGGER_TOKEN>
Content-Type: application/json
```

```json
{
  "records": [
    {
      "knox_id": "knox.user",
      "department": "Dept",
      "line": "Line",
      "user_sdwt_prod": "G-A",
      "source_updated_at": "2026-05-08T00:00:00Z"
    }
  ]
}
```

## 오류

| Status | 상황 |
| --- | --- |
| 400 | 잘못된 소속/입력 |
| 401 | 로그인 필요 |
| 403 | 관리/승인 권한 없음 |
| 404 | 대상 사용자 또는 변경 요청 없음 |
| 409 | 재확인 대상이 아님 |

## 관련 모듈 문서

- `docs/modules/account.md`
