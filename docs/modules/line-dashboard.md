# Line Dashboard / Drone 모듈

Line Dashboard는 Drone SOP 데이터를 보고, 조기 알림과 멀티 채널 알림을 관리하는 기능입니다.

## 기능 요약

- 라인 대시보드 테이블 조회/수정
- 라인 히스토리 집계
- 조기 알림 설정
- SOP POP3 수집
- SOP 대상 소속 계산
- Jira/Messenger/Mail 알림 전송
- 알림 대상/수신자 관리
- 실패 채널 재시도

## SOP 알림 흐름

1. POP3 또는 더미 API에서 SOP 메일을 수집합니다.
2. 메일 내용에서 SOP 데이터를 파싱합니다.
3. `drone_sop`에 저장하거나 갱신합니다.
4. `sdwt_prod`를 `target_user_sdwt_prod`로 해석합니다.
5. 채널별 전송 후보를 계산합니다.
6. Jira, Messenger, Mail을 독립적으로 전송합니다.
7. 채널별 성공/실패 사유를 저장합니다.

## 테이블 수정 흐름

1. 테이블명과 컬럼명을 검증합니다.
2. 허용된 컬럼만 업데이트합니다.
3. 변경 전/후 row를 조회합니다.
4. ActivityLog에 기록합니다.

## 주요 상태

| 상태 필드 | 의미 |
| --- | --- |
| `send_jira` | Jira 전송 상태 |
| `send_messenger` | Messenger 전송 상태 |
| `send_mail` | Mail 전송 상태 |
| `instant_inform` | 즉시 인폼 큐잉 여부 |
| `needtosend` | 전송 필요 여부 |

## 화면/API/데이터 추적

| 구간 | 위치 |
| --- | --- |
| 화면 | `/ESOP_Dashboard/**` |
| Frontend | `apps/web/src/features/line-dashboard` |
| Backend API | `/api/v1/line-dashboard/**` |
| 데이터 | `DroneSOP`, `DroneSopTarget`, `DroneSopTargetChannelConfig`, `DroneSopTargetRecipient`, `DroneSopTargetDispatch`, `DroneSopDelivery`, `DroneEarlyInform` |
| 외부 연동 | POP3, Jira, Knox Messenger, Knox Mail API |

## 운영 포인트

- 수집 문제는 `sop/ingest/pop3/trigger`와 POP3 env를 확인합니다.
- 전송 문제는 channel별 delivery 상태와 Jira/Messenger/Mail env를 분리해 확인합니다.
- 알림 대상 문제는 Account 소속, target mapping, recipient 설정을 함께 확인합니다.
- 테이블 수정 문제는 허용 컬럼과 ActivityLog 기록 여부를 확인합니다.

## Drone target seed

운영 초기 주입은 `seed_drone_targets_from_file` command를 사용합니다.
JSON에는 `department`, `line`, `user_sdwt_prod`만 작성하고, command가 다음 데이터를 자동 생성합니다.

- `drone_sop_target`
- `drone_sop_target_mapping`
- `drone_sop_target_channel_config`
- `drone_sop_needtosend_rule`
- `drone_sop_target_recipient`

수신인은 JSON의 `department + user_sdwt_prod` 조합으로 account 활성 사용자와
external affiliation snapshot에서 자동 수집합니다.

실행 예시:

```bash
docker compose -f docker-compose.dev.yml exec -T api \
  python manage.py seed_drone_targets_from_file \
  --file /app/config/drone_targets.json \
  --dry-run

docker compose -f docker-compose.dev.yml exec -T api \
  python manage.py seed_drone_targets_from_file \
  --file /app/config/drone_targets.json
```

이 command는 실행 시 기존 Drone SOP/발송 이력/알림 설정을 초기화합니다.
운영 반영 전 `--dry-run`으로 삭제/생성 카운트를 확인해야 합니다.

샘플 파일:

- `docs/examples/drone_targets.sample.json`

## 관련 API

- `docs/api/line-dashboard.md`

## 관련 코드

- `apps/api/api/drone/views.py`
- `apps/api/api/drone/models.py`
- `apps/api/api/drone/selectors.py`
- `apps/api/api/drone/serializers.py`
- `apps/api/api/drone/services/pop3/sop_pop3.py`
- `apps/api/api/drone/services/inform/sop_inform.py`
- `apps/api/api/drone/services/inform/retry_channel.py`
- `apps/api/api/drone/services/jira/sop_jira.py`
- `apps/api/api/drone/services/messenger/messenger_sender.py`
- `apps/api/api/drone/services/mail/mail_sender.py`
- `apps/api/api/drone/services/channels/recipients.py`
- `apps/api/api/drone/services/table_ops.py`
- `apps/web/src/features/line-dashboard`
