# API 공통 호출 규칙

이 문서는 모든 API에 공통으로 적용되는 호출 규칙입니다. 모듈별 상세 endpoint는 같은 폴더의 `*.md` 문서를 봅니다.

## Base URL

로컬 개발 기본값:

```text
http://localhost:8000
```

업무 API prefix:

```text
/api/v1
```

예외:

```text
/auth/google/callback/
```

OIDC provider가 `form_post`로 호출하는 callback입니다.

## 인증 방식

| 방식 | 사용처 | 설명 |
| --- | --- | --- |
| Django session | 일반 웹 API | OIDC 로그인 후 브라우저 쿠키 기반 |
| Airflow Bearer token | 수집/동기화 trigger | `Authorization: Bearer <AIRFLOW_TRIGGER_TOKEN>` |
| Internal token | OCR worker | `X-Internal-Token: <EMAIL_OCR_INTERNAL_TOKEN>` |
| 공개 | health, 일부 조회 | 인증 없이 접근 가능 |

## 요청 형식

대부분의 write API는 JSON body를 사용합니다.

```http
Content-Type: application/json
```

프론트 호환을 위해 일부 API는 `snake_case`와 `camelCase`를 함께 허용합니다. 모듈별 문서에 별도 표기합니다.

## 응답 형식

기본 응답은 JSON입니다.

```json
{
  "results": []
}
```

파일/이미지 endpoint는 바이너리 또는 redirect를 반환할 수 있습니다.

## 공통 오류

| Status | 의미 |
| --- | --- |
| 400 | 잘못된 요청 body/query |
| 401 | 인증 필요 |
| 403 | 권한 없음 |
| 404 | 대상 없음 |
| 409 | 현재 상태와 맞지 않는 요청 |
| 500 | 서버 처리 실패 |
| 502 | 외부 연동 실패 |
| 503 | 필수 외부 연동 설정 누락 |

## 모듈별 API 문서

- `docs/api/auth.md`
- `docs/api/account.md`
- `docs/api/emails.md`
- `docs/api/assistant.md`
- `docs/api/line-dashboard.md`
- `docs/api/timeline.md`
- `docs/api/appstore.md`
- `docs/api/voc.md`
- `docs/api/activity-health.md`
