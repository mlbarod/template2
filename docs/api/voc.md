# VOC API

VOC API는 게시글과 답변을 관리합니다.

## 호출자

- 브라우저 SPA

## 인증

게시글 생성, 수정, 삭제, 답변 작성에는 Django session이 필요합니다.

## Endpoint

| Method | Path | 설명 |
| --- | --- | --- |
| GET | `/api/v1/voc/posts` | 게시글 목록 |
| POST | `/api/v1/voc/posts` | 게시글 생성 |
| PATCH | `/api/v1/voc/posts/<post_id>` | 게시글 수정 |
| DELETE | `/api/v1/voc/posts/<post_id>` | 게시글 삭제 |
| POST | `/api/v1/voc/posts/<post_id>/replies` | 답변 작성 |

## 게시글 생성

```json
{
  "title": "문의 제목",
  "content": "문의 내용",
  "status": "접수"
}
```

허용 상태:

- `접수`
- `진행중`
- `완료`
- `반려`

## 목록 조회

```http
GET /api/v1/voc/posts?status=접수
```

응답에는 게시글 목록과 상태별 카운트가 포함됩니다.

## 권한

- 게시글 수정/삭제: 작성자 또는 관리자
- 답변 작성: 인증 사용자

## 오류

| Status | 상황 |
| --- | --- |
| 400 | 잘못된 상태 또는 입력 |
| 401 | 로그인 필요 |
| 403 | 작성자/관리자 권한 없음 |
| 404 | 게시글 없음 |

## 관련 모듈 문서

- `docs/modules/voc.md`
