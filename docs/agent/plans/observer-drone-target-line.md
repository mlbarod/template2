# ExecPlan: Observer Drone Target Line

## 목표
- Observer drill-down의 Line/SDWT 기준을 TIP status와 동일하게 `drone_target.line_id`와 `drone_target.target_user_sdwt_prod`로 통일한다.

## 현재 상태
- `list_lines`, `list_sdwt_for_line`은 Drone TIP status 옵션을 사용한다.
- `list_equipments`, `get_equipment_info`는 `mes_line_mapping_info.gpm_line_name`을 `lineId`로 반환해 드롭다운 선택값과 충돌할 수 있다.

## 범위
- 수정 영역: `apps/api/api/observer/selectors.py`, `apps/api/api/observer/views.py`, `apps/api/api/observer/tests.py`, Observer API/module docs
- 수정하지 않는 영역: DB schema, migration, frontend UI 구조, Drone target 모델

## 설계
- Observer Line은 `drone_target.line_id`를 canonical 값으로 사용한다.
- Observer SDWT는 `drone_target.target_user_sdwt_prod`를 사용한다.
- station 연결은 `drone_target.target_user_sdwt_prod = station_master.sdwt_prod_lookup` 기준으로 한다.
- `equipment-info`도 station의 SDWT를 Drone target 옵션으로 역해석해 Line/SDWT를 반환한다.

## 실행 단계
- [x] Drone target 옵션 해석 helper 추가
- [x] PRC/EQP/equipment-info selector를 새 기준으로 변경
- [x] selector/view 테스트 갱신
- [x] Docker Compose api 컨테이너에서 Observer 테스트 실행
- [x] Observer API/module 문서 갱신

## 검증
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py test api.observer`
- 필요 시 `npm run agent:audit:api-boundary`

## 위험과 대응
- 위험: 같은 `target_user_sdwt_prod`가 여러 line에 있으면 eqp-only URL에서 line 결정이 모호하다.
- 대응: line-scoped 조회는 해당 line을 우선하고, eqp-only 조회는 정렬된 첫 Drone target line을 사용한다.

## 진행 기록
- 2026-06-28: Observer 선택 기준을 Drone target 기준으로 통일하는 계획 작성.
- 2026-06-28: selector/view/test 변경 후 `api.observer` 테스트와 API boundary audit 통과.
- 2026-06-28: Observer API/module 문서에 Drone target line/SDWT 기준 반영.
