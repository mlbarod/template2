# Assistant API

Assistant API는 RAG 검색과 LLM 호출을 조합해 채팅 답변을 생성합니다.

## 호출자

- 브라우저 SPA

## 인증

Django session이 필요합니다. `knox_id`가 없는 사용자는 접근이 제한될 수 있습니다.

## Endpoint

| Method | Path | 설명 |
| --- | --- | --- |
| GET | `/api/v1/assistant/rag-indexes` | 선택 가능한 RAG 인덱스/권한 그룹 |
| POST | `/api/v1/assistant/chat` | 채팅 답변 생성 |

## RAG 인덱스 목록

```http
GET /api/v1/assistant/rag-indexes
```

응답에는 사용자가 선택할 수 있는 RAG index, 기본 index, permission group이 포함됩니다.

## 채팅 요청

```http
POST /api/v1/assistant/chat
Content-Type: application/json
```

```json
{
  "prompt": "최근 메일에서 이슈 요약해줘",
  "roomId": "room-1",
  "ragIndexNames": ["rp-emails"],
  "permissionGroups": ["G-A", "knox.user"]
}
```

주요 필드:

| Field | 설명 |
| --- | --- |
| `prompt` | 사용자 질문 |
| `roomId` | 대화방 식별자 |
| `history` | 선택적 대화 이력 |
| `ragIndexName`, `ragIndexNames` | 검색할 RAG 인덱스 |
| `permissionGroups` | 검색 허용 그룹 |

## 응답

```json
{
  "reply": "답변",
  "contexts": [],
  "sources": [],
  "segments": [],
  "meta": {}
}
```

## 권한 규칙

요청한 permission group은 서버가 계산한 접근 가능 그룹 안에 있어야 합니다.

서버가 기본으로 계산하는 그룹:

- 사용자의 접근 가능한 `user_sdwt_prod`
- 사용자의 `knox_id`
- `rag-public`

## 오류

| Status | 상황 |
| --- | --- |
| 400 | prompt 누락, 형식 오류 |
| 401 | 로그인 필요 |
| 403 | permission group 접근 불가 또는 `knox_id` 없음 |
| 502 | RAG/LLM 호출 실패 |
| 503 | RAG/LLM 설정 누락 |

## 관련 모듈 문서

- `docs/modules/assistant.md`
