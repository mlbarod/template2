# ExecPlan: Drone CTTTM URL Persist

## 목표
- Drone SOP POP3 수집 시 CTTTM URL을 미리 계산해 `drone_sop`에 저장한다.
- `/ESOP_Dashboard/status` 테이블에서 CTTTM 링크를 Defect 링크처럼 아이콘 클릭 후 호기 선택 방식으로 열 수 있게 한다.

## 현재 상태
- `drone_sop`에는 Defect 링크 저장용 `defect_url`은 있으나 CTTTM URL 저장 컬럼은 없다.
- CTTTM URL은 발송 직전 `apps/api/api/drone/services/jira/ctttm.py`에서 row의 임시 `url` 필드로만 보강된다.
- 알림 템플릿은 `row["url"]` 기반 `ctttm_urls` 컨텍스트를 사용한다.
- 상태 테이블은 `drone_sop`의 컬럼 목록을 그대로 가져오므로 DB 컬럼 추가 후 프론트 렌더러가 필요하다.

## 범위
- 수정할 영역: `api.drone` 모델/마이그레이션/selector/service/tests, line-dashboard 테이블 컬럼 렌더링.
- 수정하지 않을 영역: 기존 발송 채널 정책, CTTTM base URL/env contract, 기존 row backfill command.

## 설계
- `DroneSOP.ctttm_urls`는 여러 호기 링크를 저장할 수 있도록 `JSONField(null=True, blank=True)`로 추가한다.
- 저장 형식은 `[{"eqp_id": "...", "url": "..."}]`를 유지한다.
- POP3 row 생성 후 CTTTM 조회가 실패해도 SOP 저장은 계속 진행한다.
- 알림 컨텍스트는 `ctttm_urls`를 우선 사용하고 기존 `url` 필드를 fallback으로 둔다.
- 상태 테이블은 `ctttm_urls` 컬럼을 CTTTM 링크 버튼으로 렌더링한다.

## 실행 단계
- [x] `DroneSOP` 모델과 새 migration에 `ctttm_urls` 추가
- [x] CTTTM 최신 workorder 조회 selector 추가
- [x] POP3 row 보강 및 upsert 컬럼 추가
- [x] 알림 컨텍스트가 저장된 CTTTM URL을 우선 사용하도록 변경
- [x] 프론트 상태 테이블 CTTTM 컬럼 렌더러 추가
- [x] 상태 테이블 API 응답에서 `ctttm_urls` JSON 문자열을 배열로 정규화
- [x] 관련 테스트 추가/수정

## 검증
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py test api.drone --keepdb`
- `scripts/agent/check_ui_consistency.sh`

## 위험과 대응
- 위험: CTTTM 외부 테이블 조회 실패가 수집 실패로 전파될 수 있다.
- 대응: CTTTM 보강 함수 내부에서 예외를 로깅하고 row 저장을 계속한다.
- 위험: 기존 발송 템플릿이 `url` 필드만 기대한다.
- 대응: 보강 시 `ctttm_urls`와 `url`을 함께 채우고 컨텍스트는 양쪽을 모두 지원한다.

## 진행 기록
- 2026-05-27: 사용자 결정 반영. JSONField 저장, CTTTM 조회 실패 시 저장 계속, backfill 제외.
- 2026-05-27: `ctttm_urls` 모델/migration, POP3 보강, status 테이블 렌더러, 테스트를 추가.
- 2026-05-27: `api.drone` 테스트 254개, UI consistency audit, migration dry-run 검증 통과.
- 2026-05-27: CTTTM `url` 호환 경로를 제거하고 `ctttm_urls`를 단일 소스로 정리.
- 2026-05-28: `/line-dashboard/tables` 응답에서 raw cursor의 `ctttm_urls` 문자열 JSON을 배열로 보정.
