# ExecPlan: Airflow 단순 실패 알림

## 목표
- API 내부 상세 실패 알림을 제거하고 Airflow `on_failure_callback` 기반 단순 장애 감지 알림으로 전환한다.

## 현재 상태
- Airflow DAG들은 API 호출 후 `response.raise_for_status()`로 task 실패를 발생시킨다.
- 직전 구현으로 API view와 common service에 Knox 메신저 상세 알림이 추가되어 있다.

## 범위
- 수정: Airflow DAG 공통 실패 callback, 관련 DAG `default_args`, 직전 API 상세 알림 제거, env/docs 정리.
- 제외: DB schema, auth contract, Airflow retry 정책 변경.

## 설계
- DAG task 실패 시 callback이 DAG/task/run/log URL 중심의 단순 메시지를 Knox 메신저로 전송한다.
- 수신자는 `AIRFLOW_FAILURE_ALERT_KNOX_IDS`로 설정한다.
- 최초 생성된 chatroom_id는 `AIRFLOW_FAILURE_ALERT_CHATROOM_ID_FILE` JSON 메모 파일에 저장해 재사용한다.
- API는 기존처럼 실패 시 500만 반환하고 알림은 보내지 않는다.

## 실행 단계
- [x] Airflow 공통 실패 callback 모듈 추가
- [x] 모든 API-trigger DAG의 `default_args`에 callback 연결
- [x] API 상세 알림 서비스/호출/테스트 제거
- [x] env/docs를 Airflow callback 설정으로 정리
- [x] 구문 검사와 관련 테스트/audit 실행

## 검증
- `python3 -m py_compile`로 변경 Python 파일 구문 검사
- `docker compose -f docker-compose.dev.yml run --rm --entrypoint "" api python manage.py test ...`
- `npm run agent:audit:api-boundary`

## 위험과 대응
- 위험: Airflow 컨테이너에서 Knox env가 없으면 알림이 스킵된다.
- 대응: env/docs에 Airflow callback 설정을 명시한다.
- 위험: 메모 파일이 컨테이너 재생성 시 사라지면 채팅방이 다시 생성된다.
- 대응: `AIRFLOW_FAILURE_ALERT_CHATROOM_ID_FILE`을 persistent mount 경로로 지정할 수 있게 한다.

## 진행 기록
- 2026-07-09: 단순 장애 감지를 위해 API 상세 알림에서 Airflow callback 방식으로 전환하기로 결정했다.
- 2026-07-09: Airflow DAG 공통 callback을 추가하고 API 상세 알림 코드를 제거했다.
- 2026-07-09: Python 구문 검사, Airflow 이미지 내 DAG import, backend boundary audit를 통과했다.
- 2026-07-09: `env/airflow.common.env`를 추가하고 Airflow DAG/callback env를 Compose inline 설정에서 분리했다.
