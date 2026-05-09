# Auth API

Auth API는 OIDC 로그인과 Django session 관리를 담당합니다.

## 호출자

- 브라우저 SPA
- OIDC provider callback

## Endpoint

| Method | Path | Auth | 설명 |
| --- | --- | --- | --- |
| GET | `/api/v1/auth/config` | 공개 | 프론트 인증 설정 조회 |
| GET | `/api/v1/auth/login` | 공개 | OIDC 로그인 시작 |
| POST | `/auth/google/callback/` | OIDC form_post | OIDC callback 처리 |
| GET | `/api/v1/auth/me` | Session | 현재 사용자 조회 |
| GET | `/api/v1/auth/logout` | Session | 로그아웃 후 IdP logout redirect |
| POST | `/api/v1/auth/logout` | Session | 로그아웃 URL JSON 반환 |
| GET | `/api/v1/auth/` | 공개 | 프론트 redirect 보조 |

## 로그인 시작

```http
GET /api/v1/auth/login?target=/account
```

동작:

1. OIDC 설정 여부를 확인합니다.
2. `target` 또는 `next`를 state로 인코딩합니다.
3. nonce를 세션에 저장합니다.
4. ADFS authorize URL로 redirect합니다.

## Callback

```http
POST /auth/google/callback/
Content-Type: application/x-www-form-urlencoded
```

OIDC provider가 `id_token`, `state`를 form_post로 전달합니다.

동작:

1. state와 redirect target을 검증합니다.
2. 세션 nonce와 id_token nonce를 비교합니다.
3. claim으로 `User`를 생성하거나 갱신합니다.
4. Django session login 후 target으로 redirect합니다.

## 현재 사용자

```http
GET /api/v1/auth/me
```

응답에는 사용자 기본 정보와 소속 상태가 포함됩니다.

```json
{
  "isAuthenticated": true,
  "user": {
    "id": 1,
    "username": "user",
    "knoxId": "knox.user",
    "userSdwtProd": "G-A"
  }
}
```

## 오류

| Status | 상황 |
| --- | --- |
| 400 | callback 값 누락 또는 state 오류 |
| 401 | 로그인되지 않은 상태에서 `/me` 호출 |
| 403 | 허용되지 않은 redirect target |
| 503 | OIDC provider 설정 누락 |

## 관련 모듈 문서

- `docs/modules/auth.md`
