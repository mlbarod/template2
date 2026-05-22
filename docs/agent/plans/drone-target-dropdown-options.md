# ExecPlan: Drone Target Dropdown Options

## 목표
- Engr분임조/설비분임조 조합 드롭다운 후보를 `drone_sop_target` 기준으로만 제공한다.
- 기존 `drone_sop_target_mapping`, `drone_sop`, `account_affiliation` 기반 후보가 드롭다운에 섞이지 않게 한다.

## 현재 상태
- `GET /api/v1/line-dashboard/notification-targets`의 `mappingOptions`는 `drone_sop_target`, mapping, 실제 SOP 관측값을 합쳐 반환한다.
- 프론트의 조합 드롭다운 line 옵션은 `account_affiliation` 기반 `/api/v1/account/line-sdwt-options`도 사용한다.

## 범위
- 수정: Drone selector/view 응답, line-dashboard API 정규화, line settings hook/page, 관련 테스트.
- 제외: DB schema/migration, mapping 생성/삭제 API body, 수신인 후보 API.

## 설계
- 현재 line의 `mappingOptions.userSdwtProds`와 `mappingOptions.sdwtProds`는 둘 다 해당 line의 `DroneSopTarget.target_user_sdwt_prod`만 사용한다.
- 모든 line의 드롭다운 line 옵션은 `DroneSopTarget.line_id`와 `target_user_sdwt_prod`만 그룹화해 `mappingOptionLines`로 내려준다.
- 프론트는 account affiliation 옵션 호출을 제거하고 `mappingOptionLines`를 사용한다.

## 실행 단계
- [x] Backend selector/view 응답을 `drone_sop_target` 기준으로 변경한다.
- [x] Frontend API/hook/page가 `mappingOptionLines`를 사용하도록 변경한다.
- [x] Backend focused test를 갱신한다.
- [x] Lint/audit/backend test를 실행한다.

## 검증
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py test api.drone.tests.DroneNotificationTargetEndpointTests --keepdb`
- `npm run web:lint`
- `npm run agent:audit:ui`

## 위험과 대응
- 위험: 기존 mapping/SOP에서만 관측된 값은 드롭다운에서 사라진다.
- 대응: 사용자가 요청한 기준인 `drone_sop_target` seed/생성 값을 단일 소스로 사용한다.

## 진행 기록
- 2026-05-22: `drone_sop_target` 기준 드롭다운 데이터 소스로 변경하기로 했다.
- 2026-05-22: backend/frontend 변경과 focused 검증이 통과했다.
- 2026-05-22: `DroneSopTargetRecipientTests`, web lint, UI audit, frontend boundary audit가 통과했다.
