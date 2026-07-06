# ExecPlan: ct_process_comment summary format

## 목표
- `ct_process_comment.llm_summary`가 `시간순 요약:`으로 시작하지 않도록 한다.
- Log Detail streaming에서 요약 이벤트가 `[시간] 이벤트` 형식으로 줄바꿈 표시되도록 한다.
- 각 timestamp chunk는 모두 출력하되 chunk별 내용은 한 줄로 짧게 유지한다.
- `contents_text`의 `[ YYYY-MM-DD HH:MM / 작성자 ]` header 다음 내용을 다음 header 전까지 같은 시간 이벤트로 처리한다.

## 현재 상태
- Airflow DAG `airflow/dags/ct_process_comment_summary.py`는 요약 API만 호출한다.
- 실제 요약 프롬프트와 저장 로직은 `apps/api/api/data_movement/ct_process_comment/services/summary.py`에 있다.
- Observer Log Detail streaming은 `apps/web/src/features/observer/components/StreamingText.jsx`가 텍스트를 표시한다.

## 범위
- 수정: `summary.py`, 관련 backend test, `StreamingText.jsx`.
- 제외: DB schema, API route/response contract, Airflow schedule/env contract 변경.

## 설계
- OpenWebUI prompt를 timestamp chunk마다 `[시간] 이벤트` 한 줄을 출력하는 형식으로 바꾼다.
- 저장 전 정규화로 기존 응답의 `시간순 요약:` prefix와 구형 원인/조치사항/결과 항목을 제거한다.
- frontend streaming 텍스트는 newline을 보존하는 Tailwind whitespace class를 사용한다.
- LLM 요청 전 `contents_text`를 `[YYYY-MM-DD HH:MM] 이벤트 내용` timeline으로 변환해 시간 해석을 deterministic하게 만든다.
- prompt에서 `[시간 미상]` 관련 지시는 제거한다.

## 실행 단계
- [x] 요약 프롬프트와 저장 전 정규화 로직 수정
- [x] service test 기대값 수정
- [x] streaming 표시에서 줄바꿈 보존
- [x] 관련 검증 실행

## 검증
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py test api.data_movement.ct_process_comment --keepdb`
- `npm run agent:audit:ui`

## 위험과 대응
- 위험: LLM이 이전 형식으로 응답할 수 있다.
- 대응: 저장 전 정규화에서 prefix 제거와 이벤트 줄 변환을 수행한다.

## 진행 기록
- 2026-07-06: 사용자 요청에 따라 요약 저장/표시 포맷 조정을 시작했다.
- 2026-07-06: 프롬프트, 저장 전 정규화, frontend 줄바꿈 표시를 수정했다.
- 2026-07-06: `api.data_movement.ct_process_comment` 테스트와 Python compile 검증은 통과했다. UI audit은 기존 `l3-spider` raw color/inline style 후보로 실패했다.
- 2026-07-06: `contents_text` comment header를 timestamped event로 변환하도록 계획을 확장했다.
- 2026-07-06: timestamped event 변환 테스트를 추가하고 `api.data_movement.ct_process_comment` 22건 테스트를 통과했다.
- 2026-07-06: 전체 최대 3줄 제한을 제거하고 timestamp chunk별 한 줄 요약으로 변경했다.
