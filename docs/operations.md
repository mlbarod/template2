# 운영/개발 명령

이 문서는 로컬 실행, 테스트, 마이그레이션 확인, management command를 정리합니다.

## 로컬 실행

```bash
docker compose -f docker-compose.dev.yml up -d
```

주요 주소:

| 서비스 | 주소 |
| --- | --- |
| Web | `http://localhost:3000` |
| API | `http://localhost:8000` |
| Nginx | `http://localhost` |
| Dummy ADFS/RAG/LLM/Mail/Jira | `http://localhost:9102` |
| MinIO | `http://localhost:9000`, `http://localhost:9001` |

## 프론트 명령

```bash
npm run web:dev
npm run web:build
npm run web:lint
```

## 백엔드 검증

백엔드는 Docker Compose `api` 컨테이너 기준입니다.

```bash
docker compose -f docker-compose.dev.yml exec -T api python manage.py check
docker compose -f docker-compose.dev.yml exec -T api python manage.py test
docker compose -f docker-compose.dev.yml exec -T api python manage.py makemigrations --check --dry-run
```

## Management command

| Command | 설명 |
| --- | --- |
| `seed_dummy_emails` | 개발용 샘플 메일 생성 |
| `process_email_outbox` | EmailOutbox RAG 작업 처리 |
| `seed_drone_dummy_data` | Drone 개발용 샘플 데이터 생성 |

실행 예시:

```bash
docker compose -f docker-compose.dev.yml exec -T api python manage.py seed_dummy_emails
docker compose -f docker-compose.dev.yml exec -T api python manage.py process_email_outbox
docker compose -f docker-compose.dev.yml exec -T api python manage.py seed_drone_dummy_data
```

## 환경 변수 파일

| 파일 | 역할 |
| --- | --- |
| `env/api.common.env` | API 공통 설정 |
| `env/api.dev.env` | API 개발 오버라이드 |
| `env/web.dev.env` | Web 개발 설정 |
| `minio.env` | MinIO 설정 |

## 주의할 점

- backend 테스트와 Django 명령은 `api` 컨테이너에서 실행합니다.
- 외부 연동 URL은 하드코딩하지 않고 env로 관리합니다.
- auth/RAG/assistant/mail 계약을 바꾸면 `apps/adfs_dummy`도 함께 갱신합니다.
