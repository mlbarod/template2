# Assistant / RAG 모듈

Assistant는 사용자 질문을 받아 RAG 검색을 수행하고 LLM 답변을 생성합니다. RAG app은 외부 RAG 서버를 호출하는 공통 client입니다.

## 기능 요약

- 사용 가능한 RAG index 조회
- permission group 검증
- RAG 검색
- LLM 호출
- 답변/출처/segment 반환
- 사용자/room 단위 대화 이력 관리

## 권한 기준

Assistant는 다음 값을 permission group으로 사용합니다.

- 접근 가능한 `user_sdwt_prod`
- 사용자의 `knox_id`
- `rag-public`

요청 permission group이 이 범위를 벗어나면 거부합니다.

## 채팅 흐름

1. 사용자가 `prompt`를 보냅니다.
2. 서버가 사용자와 `knox_id`를 확인합니다.
3. permission group과 RAG index를 검증합니다.
4. 기존 대화 이력을 가져옵니다.
5. RAG 검색을 수행합니다.
6. 검색 결과를 LLM에 전달합니다.
7. 답변, 출처, segment, meta를 반환합니다.

## RAG client 역할

- RAG 검색
- Email 문서 insert
- 문서 delete
- index/permission group 정규화
- 실패 로그 기록

## 관련 API

- `docs/api/assistant.md`

## 관련 코드

- `apps/api/api/assistant/views.py`
- `apps/api/api/assistant/services/chat.py`
- `apps/api/api/assistant/services/config.py`
- `apps/api/api/assistant/services/memory.py`
- `apps/api/api/assistant/services/normalization.py`
- `apps/api/api/assistant/services/reply.py`
- `apps/api/api/rag/services/client.py`
- `apps/api/api/rag/services/config.py`
- `apps/web/src/features/assistant`
