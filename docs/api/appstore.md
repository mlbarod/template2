# AppStore API

AppStore API는 내부 앱 등록, 조회, 댓글, 좋아요 기능을 제공합니다.

## 호출자

- 브라우저 SPA

## 인증

- 목록/상세 조회는 비로그인 접근도 일부 허용될 수 있습니다.
- 등록, 수정, 삭제, 좋아요, 댓글 작성은 로그인 사용자가 필요합니다.

## Endpoint

| Method | Path | 설명 |
| --- | --- | --- |
| GET | `/api/v1/appstore/apps` | 앱 목록 |
| POST | `/api/v1/appstore/apps` | 앱 등록 |
| GET | `/api/v1/appstore/apps/<app_id>` | 앱 상세 |
| PATCH | `/api/v1/appstore/apps/<app_id>` | 앱 수정 |
| DELETE | `/api/v1/appstore/apps/<app_id>` | 앱 삭제 |
| GET | `/api/v1/appstore/apps/<app_id>/cover` | 대표 이미지 |
| POST | `/api/v1/appstore/apps/<app_id>/like` | 앱 좋아요 토글 |
| POST | `/api/v1/appstore/apps/<app_id>/view` | 조회수 증가 |
| GET | `/api/v1/appstore/apps/<app_id>/comments` | 댓글 목록 |
| POST | `/api/v1/appstore/apps/<app_id>/comments` | 댓글 작성 |
| PATCH | `/api/v1/appstore/apps/<app_id>/comments/<comment_id>` | 댓글 수정 |
| DELETE | `/api/v1/appstore/apps/<app_id>/comments/<comment_id>` | 댓글 삭제 |
| POST | `/api/v1/appstore/apps/<app_id>/comments/<comment_id>/like` | 댓글 좋아요 토글 |

## 앱 등록 요청

```json
{
  "name": "업무 도구",
  "category": "Tools",
  "description": "설명",
  "url": "https://example.com",
  "manualUrl": "https://example.com/manual",
  "screenshotUrls": ["https://example.com/cover.png"],
  "coverScreenshotIndex": 0,
  "contactName": "홍길동",
  "contactKnoxid": "hong"
}
```

## 권한

- 앱 수정/삭제: 작성자 또는 관리자
- 댓글 수정/삭제: 작성자 또는 관리자
- 좋아요: 로그인 사용자

## 오류

| Status | 상황 |
| --- | --- |
| 400 | 필수값 누락 또는 잘못된 이미지 |
| 401 | 로그인 필요 |
| 403 | 작성자/관리자 권한 없음 |
| 404 | 앱 또는 댓글 없음 |

## 관련 모듈 문서

- `docs/modules/appstore.md`
