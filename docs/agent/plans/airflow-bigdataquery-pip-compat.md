# ExecPlan: Airflow BigDataQuery pip compatibility

## 목표
- OIDC/prod Airflow 이미지 빌드가 `pip install bigdataquery`를 수행할 때 신규 PyPI mirror와 기존 `repo.samsungds.net` PyPI repository를 당분간 함께 참조하게 한다.

## 현재 상태
- `airflow/Dockerfile`은 pip index 설정만 만들고 `bigdataquery` Python 패키지를 설치하지 않는다.
- `compose/airflow.internal.yml`은 OIDC/prod Airflow build arg로 `PIP_INDEX_URL`만 전달한다.
- dev Airflow compose는 공식 `apache/airflow:2.11.0` 이미지를 직접 사용하며 변경 대상이 아니다.

## 범위
- 수정: `airflow/Dockerfile`, `compose/airflow.internal.yml`, `docs/configuration.md`
- 제외: dev Airflow compose, DAG 코드, API/Web 코드, ODBC driver artifact URL 변경

## 설계
- Dockerfile에 `PIP_EXTRA_INDEX_URL`, `INSTALL_BIGDATAQUERY_PYTHON` build arg를 추가한다.
- pip config는 primary `index-url`과 optional `extra-index-url`을 함께 기록한다.
- internal compose에서는 기존 `repo.samsungds.net` PyPI simple URL을 `PIP_EXTRA_INDEX_URL`에 임시로 하드코딩한다.
- `INSTALL_BIGDATAQUERY_PYTHON=true`일 때 `bigdataquery`를 직접 설치한다.

## 실행 단계
- [x] 이전 ODBC fallback 변경 제거
- [x] Dockerfile pip extra index와 `bigdataquery` 설치 로직 추가
- [x] internal Airflow compose build arg 추가
- [x] 환경 설정 문서 갱신
- [x] Compose config 검증

## 검증
- `bash scripts/agent/check_compose_configs.sh`
- 기대 결과: dev/OIDC/prod Compose 병합 결과가 정상이고, OIDC/prod Airflow build arg에 `INSTALL_BIGDATAQUERY_PYTHON`, `PIP_EXTRA_INDEX_URL`이 표시된다.

## 위험과 대응
- 위험: 기존 `repo.samsungds.net` PyPI repository 경로가 바뀌면 Airflow 이미지 빌드가 실패할 수 있다.
- 대응: 신규 mirror 적재 완료 후 하드코딩한 `PIP_EXTRA_INDEX_URL`을 제거한다.

## 진행 기록
- 2026-07-09: 사용자 정정으로 대상이 ODBC artifact가 아니라 `pip install bigdataquery` 호환임을 확인했다.
- 2026-07-09: ODBC artifact fallback 변경을 제거하고, Airflow Dockerfile에 `PIP_EXTRA_INDEX_URL`과 `bigdataquery` Python package 설치 옵션을 추가했다.
- 2026-07-09: `bash scripts/agent/check_compose_configs.sh`가 통과했고, OIDC/prod compose config에서 `INSTALL_BIGDATAQUERY_PYTHON=true`와 legacy `PIP_EXTRA_INDEX_URL` build arg를 확인했다.
- 2026-07-09: `PIP_EXTRA_INDEX_URL`을 env override 없이 기존 `repo.samsungds.net` PyPI simple URL로 임시 고정했다.
