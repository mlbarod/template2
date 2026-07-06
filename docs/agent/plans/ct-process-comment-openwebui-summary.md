# ExecPlan: ct_process_comment OpenWebUI summary batch

## 목표
- `ct_process_comment.update_flag='Y'` row를 최근 업데이트 순으로 OpenWebUI에 요약 요청한다.
- 성공 시 `llm_summary`를 저장하고 `update_flag='N'`으로 변경한다.
- Observer CTTTM log detail에서 기존 `summary` 필드로 저장된 요약을 사용한다.

## 현재 상태
- `ct_process_comment`에는 `contents_text`, `llm_summary`, `update_flag`, `updated_at` 컬럼이 있다.
- loader는 신규/변경 row의 `update_flag`를 `Y`로 설정하고, `contents_text` 변경 시 `llm_summary`를 `NULL`로 초기화한다.
- Observer CTTTM selector는 `ct_process_comment.llm_summary as summary`를 이미 조회한다.
- CTTTM detail UI는 `log.summary`를 이미 표시한다.

## 범위
- 수정: `ct_process_comment` selector/service/management command/tests, data movement summary trigger API, Airflow DAG, Django settings, env/docs.
- 제외: Observer UI 구조 변경, 파일 적재 직후 자동 요약 실행, DB schema 변경.

## 설계
- 별도 `OPENWEBUI_*` 설정을 사용해 Assistant LLM 설정과 분리한다.
- 조회 순서는 `updated_at DESC, id DESC`로 고정한다.
- OpenWebUI 호출은 OpenAI 호환 chat completions 응답을 전제로 한다.
- prompt는 고정 출력 형식을 강제하고, temperature는 `0.0`으로 고정한다.
- 성공 row만 `llm_summary`와 `update_flag='N'`을 갱신한다.
- 실패 row는 `update_flag='Y'`를 유지해 다음 배치에서 재시도한다.
- `contents_text`가 비어 있는 row는 외부 호출 없이 skip하고 flag는 유지한다.
- 로컬 dev는 `adfs_dummy`의 `/v1/chat/completions`를 `OPENWEBUI_URL`로 사용한다.
- Airflow `data_movement_file_load` DAG는 `load_ct_process_comment` 성공 후 요약 trigger API를 호출한다.

## 실행 단계
- [x] ExecPlan 작성
- [x] OpenWebUI settings/env/docs 추가
- [x] pending summary selector 추가
- [x] OpenWebUI 요약 service 추가
- [x] `summarize_ct_process_comment` command 추가
- [x] Airflow summary trigger API/DAG 추가
- [x] 테스트 추가/수정
- [x] 검증 명령 실행

## 검증
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py test api.data_movement.ct_process_comment api.observer --keepdb`
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py makemigrations --check --dry-run`
- `npm run agent:audit:api-boundary`

## 위험과 대응
- 위험: 외부 API 장애가 적재 lifecycle을 막을 수 있다.
- 대응: 파일 적재와 요약을 별도 command로 분리한다.
- 위험: LLM이 입력에 없는 내용을 생성할 수 있다.
- 대응: 고정 prompt, `temperature=0.0`, 명시적 "확인 불가" 규칙을 사용한다.
- 위험: 실패 row가 처리 완료로 잘못 표시될 수 있다.
- 대응: 성공 응답을 받은 row만 `update_flag='N'`으로 변경한다.

## 진행 기록
- 2026-07-06: 사용자 결정에 따라 command 분리, `OPENWEBUI_*` 별도 설정, `updated_at DESC, id DESC` 순서로 계획했다.
- 2026-07-06: OpenWebUI 요약 service/command/env/docs/tests를 추가했고 대상 테스트, migration check, backend boundary audit을 통과했다.
- 2026-07-06: Airflow 주기 실행을 위해 `ct_process_comment/summarize/` trigger API와 DAG task를 추가했다.
