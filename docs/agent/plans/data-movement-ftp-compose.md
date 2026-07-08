# ExecPlan: data_movement FTP Compose

## 목표
- 레포 Docker Compose에서 FTP 서비스를 실행한다.
- FTP 업로드 파일이 API `data_movement` loader가 읽는 host data 폴더와 같은 경로에 쌓이도록 한다.

## 현재 상태
- API는 `/data/data_movement` 컨테이너 경로를 사용한다.
- Compose는 `DATA_MOVEMENT_HOST_PATH`를 API의 `/data/data_movement`로 mount한다.
- 기본값은 host 절대 경로 `/data/data_movement`라 레포 `data/` 폴더와 직접 연결되지 않는다.

## 범위
- 수정할 영역:
  - `docker-compose.yml`
  - `docker-compose.dev.yml`
  - `docker-compose.oidc.yml`
  - `.gitignore`
  - 관련 docs
- 수정하지 않을 영역:
  - data_movement loader 구현
  - Airflow DAG 구현
  - Portainer 서비스 추가

## 설계
- `repository.samsungds.net/proxy-docker-registry-1.docker.io/fauria/vsftpd` 이미지를 사용한다.
- FTP service는 `DATA_MOVEMENT_HOST_PATH`를 API와 동일하게 mount한다.
- 기본 host path는 `./data/data_movement`로 맞춘다.
- `FTP_PASV_ADDRESS`, `FTP_USER`, `FTP_PASS`, port range는 env로 override 가능하게 둔다.

## 실행 단계
- [x] ExecPlan 작성
- [x] Compose FTP service 추가 및 API data movement host path 기본값 정렬
- [x] data movement local data path gitignore 추가
- [x] docs 갱신
- [x] Compose config 검증

## 검증
- `docker compose -f docker-compose.yml config --services`
- `docker compose -f docker-compose.dev.yml config --services`
- `docker compose -f docker-compose.oidc.yml config --services`
- `scripts/agent/check_docs_inventory.sh`

## 위험과 대응
- 위험: 운영에서 기본 FTP 계정/비밀번호를 그대로 사용할 수 있다.
- 대응: env override 문서화와 `FTP_PASS` 변경 안내를 추가한다.
- 위험: PASV address가 배포 host와 맞지 않으면 passive 연결이 실패한다.
- 대응: `FTP_PASV_ADDRESS`를 env로 설정하도록 한다.

## 진행 기록
- 2026-05-30: FTP service를 Compose에 추가하고 API와 같은 data movement host path를 공유하도록 진행한다.
- 2026-05-30: 세 Compose 파일에 FTP service를 추가하고 기본 `DATA_MOVEMENT_HOST_PATH`를 `./data/data_movement`로 정렬했다.
- 2026-05-30: 세 Compose config와 docs inventory 검증을 통과했다.
