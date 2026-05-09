# VOC 모듈

VOC는 문의, 개선 요청, 답변을 관리하는 게시판형 기능입니다.

## 기능 요약

- 게시글 목록 조회
- 게시글 생성/수정/삭제
- 상태별 카운트 집계
- 답변 작성
- ActivityLog 기록

## 게시글 상태

- `접수`
- `진행중`
- `완료`
- `반려`

## 권한

- 게시글 생성과 답변 작성은 인증 사용자가 수행합니다.
- 게시글 수정/삭제는 작성자 또는 관리자만 가능합니다.

## 처리 흐름

1. 목록 조회 시 상태 필터를 검증합니다.
2. 게시글과 답변, 작성자를 함께 조회합니다.
3. 생성/수정/삭제 시 ActivityLog metadata를 남깁니다.
4. 답변 작성 후 갱신된 게시글 정보를 반환합니다.

## 관련 API

- `docs/api/voc.md`

## 관련 코드

- `apps/api/api/voc/views.py`
- `apps/api/api/voc/models.py`
- `apps/api/api/voc/selectors.py`
- `apps/api/api/voc/serializers.py`
- `apps/api/api/voc/services/posts.py`
- `apps/web/src/features/voc`
