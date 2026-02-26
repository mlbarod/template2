# Drone 백엔드 문서

## 개요
- `drone` 모듈은 Line Dashboard의 조기 알림 설정, 히스토리 집계, Drone SOP 수집/전송 파이프라인을 담당합니다.
- SOP 파이프라인은 `POP3 수집 -> Jira 생성 -> 멀티 채널 알림` 흐름으로 동작합니다.
- Airflow 트리거 엔드포인트는 Bearer 토큰(`ensure_airflow_token`)으로 보호합니다.

## 모듈 구조
- `views.py`: HTTP 파라미터 검증/응답 구성, 서비스 호출
- `selectors.py`: 읽기 전용 조회(QuerySet/Raw SQL)
- `services/early_inform/early_inform.py`: 조기 알림 CRUD 비즈니스 로직
- `services/pop3/sop_pop3.py`: POP3/더미 메일 수집 및 `drone_sop` 업서트
- `services/jira/sop_jira.py`: Jira 이슈 생성, 즉시 인폼 처리
- `services/inform/sop_inform.py`: Jira/메신저/메일 멀티 채널 전송
- `services/channels/user_sdwt_channel.py`: `target_user_sdwt_prod` 기준 채널 설정 upsert
- `services/shared/*`: 공통 정책/컨텍스트/대상 해석/유틸

## 엔드포인트
- `GET /api/v1/line-dashboard/early-inform`
- `POST /api/v1/line-dashboard/early-inform`
- `PATCH /api/v1/line-dashboard/early-inform`
- `DELETE /api/v1/line-dashboard/early-inform`
- `GET /api/v1/line-dashboard/history`
- `GET /api/v1/line-dashboard/line-ids`
- `GET /api/v1/line-dashboard/jira-keys`
- `POST /api/v1/line-dashboard/jira-keys`
- `GET /api/v1/line-dashboard/jira-user-sdwt-prods`
- `POST /api/v1/line-dashboard/sop/<sop_id>/instant-inform`
- `POST /api/v1/line-dashboard/sop/ingest/pop3/trigger`
- `POST /api/v1/line-dashboard/sop/jira/precheck`
- `POST /api/v1/line-dashboard/sop/jira/trigger`
- `POST /api/v1/line-dashboard/sop/inform/precheck`
- `POST /api/v1/line-dashboard/sop/inform/trigger`

## 핵심 모델
- `DroneSOP` (`drone_sop`)
  - SOP 식별키: `sop_key`
  - 전송 상태: `send_jira`, `send_messenger`, `send_mail`, `instant_inform`
  - 전송 사유: `jira_reason`, `messenger_reason`, `mail_reason`
  - 알림 관련: `jira_key`, `informed_at`, `inform_step`, `needtosend`
- `DroneSopUserSdwtProdMap` (`drone_sop_user_sdwt_map`)
  - `sdwt_prod`/`user_sdwt_prod` 조합을 `target_user_sdwt_prod`로 해석하는 규칙
- `DroneSopUserSdwtChannel` (`drone_sop_user_sdwt_channel`)
  - `target_user_sdwt_prod`별 Jira/메일/메신저 키, 템플릿, 활성 플래그
- `DroneSopNeedToSendRule` (`drone_sop_needtosend_rule`)
  - `target_user_sdwt_prod`별 needtosend 계산 규칙
- `DroneEarlyInform` (`drone_early_inform`)
  - 라인/메인스텝 기반 조기 알림 종료 스텝(`custom_end_step`) 규칙

## 주요 흐름

### 1) Early Inform CRUD
1. 요청 인증 확인
2. 파라미터 검증 및 정규화
3. 서비스(`services.early_inform`) 호출
4. ActivityLog 메타데이터 기록 후 응답

### 2) 라인 히스토리 집계
1. `table/lineId/from/to/rangeDays` 정규화
2. 테이블 스키마/타임스탬프 컬럼 검증
3. totals/breakdown SQL 생성 및 조회
4. 차트 payload 정규화 후 반환

### 3) SOP POP3 수집
1. 락 획득(`drone_sop_pop3_ingest`)
2. `dummy_mode`면 더미 API, 아니면 실제 POP3 경로 실행
3. 제목 필터 통과 메일만 파싱 (`<data>` 태그)
4. `target_user_sdwt_prod`/`needtosend` 계산 후 `drone_sop` 업서트
5. 처리된 메일 삭제 및 오래된 데이터 prune

### 4) Jira 생성 배치
1. 락 획득(`drone_sop_jira_create`)
2. 후보 조회(`send_jira=0` and 완료/즉시인폼 조건)
3. 대상 소속 해석 실패 건 즉시 실패 처리
4. 채널 계획(`project_key/template_key`) 해석
5. Jira API 호출(벌크/단건) 후 `send_jira/jira_key/inform_step/informed_at` 갱신
6. 즉시 인폼 실패 건은 `instant_inform=-1` 반영

### 5) 멀티 채널 알림 배치
1. 락 획득(`drone_sop_inform_create`)
2. 후보 조회(`send_jira/send_messenger/send_mail` 중 미전송 존재)
3. 대상 소속 해석 및 채널 설정 로딩
4. Jira/메신저/메일 채널을 독립 파이프라인으로 실행
5. 채널별 성공/실패/비활성 사유를 `send_*`/`*_reason`에 반영

### 6) 단건 즉시 인폼
1. `sop_id` 행 잠금 조회
2. 이미 Jira 전송 완료면 `already_informed` 반환
3. 미전송이면 `instant_inform=1`로 큐잉

## 설정/환경 변수
- POP3
  - `DRONE_SOP_POP3_HOST`, `DRONE_SOP_POP3_PORT`
  - `DRONE_SOP_POP3_USERNAME`, `DRONE_SOP_POP3_PASSWORD`
  - `DRONE_SOP_POP3_USE_SSL`, `DRONE_SOP_POP3_TIMEOUT`
  - `DRONE_INCLUDE_SUBJECT_PREFIXES`
  - `DRONE_SOP_DUMMY_MODE`, `DRONE_SOP_DUMMY_MAIL_MESSAGES_URL`
- Jira
  - `DRONE_JIRA_BASE_URL`, `DRONE_JIRA_TOKEN`, `DRONE_JIRA_USER`
  - `DRONE_JIRA_ISSUE_TYPE`
  - `DRONE_JIRA_USE_BULK_API`, `DRONE_JIRA_BULK_SIZE`
  - `DRONE_JIRA_CONNECT_TIMEOUT`, `DRONE_JIRA_READ_TIMEOUT`
  - `DRONE_JIRA_VERIFY_SSL`
- CTTTM
  - `DRONE_CTTTM_TABLE_NAME`, `DRONE_CTTTM_BASE_URL`
- 메일/메신저
  - `DRONE_MAIL_*`
  - `KNOX_MESSENGER_*`, `KNOX_IDM_*`

## 관련 코드 경로
- `apps/api/api/drone/views.py`
- `apps/api/api/drone/selectors.py`
- `apps/api/api/drone/models.py`
- `apps/api/api/drone/serializers.py`
- `apps/api/api/drone/services/__init__.py`
- `apps/api/api/drone/services/early_inform/early_inform.py`
- `apps/api/api/drone/services/pop3/sop_pop3.py`
- `apps/api/api/drone/services/jira/sop_jira.py`
- `apps/api/api/drone/services/inform/sop_inform.py`
