# ExecPlan: Delete Notification Target Mapping

## 목표
- Engr분임조 - 설비분임조 지정조합 뱃지 오른쪽에 삭제 버튼을 추가한다.
- 삭제 버튼 클릭 시 해당 mapping row를 실제로 삭제하고 UI 목록에서 제거한다.

## 현재 상태
- Frontend 지정조합 목록은 `apps/web/src/features/line-dashboard/components/cards/NotificationTargetCard.jsx`에서 렌더링한다.
- Frontend는 `createNotificationTargetMapping`만 가지고 있고 삭제 API wrapper/hook이 없다.
- Backend `DroneNotificationTargetMappingView`는 `POST` 생성만 제공한다.
- Backend service `target_mapping.py`는 생성 서비스만 제공한다.

## 범위
- 수정할 영역: drone target mapping 삭제 service/view/test, line-dashboard API wrapper/hook/page/card 연결.
- 수정하지 않을 영역: DB schema/migration, target/recipient/channel 설정 로직, defectmap/mail 로직.

## 설계
- API contract: `DELETE /api/v1/line-dashboard/notification-target-mappings` JSON body에 `lineId`, `targetUserSdwtProd`, `sdwtProd`, `userSdwtProd`를 받는다.
- Backend service는 line/target/pair가 일치하는 `DroneSopTargetMapping`만 삭제하고, 없으면 404 의미의 service error를 낸다.
- 응답은 생성 API와 동일하게 갱신된 `target` shape를 반환해 frontend state replacement가 가능하게 한다.
- 권한은 생성과 동일하게 `user_can_manage_drone_sop_recipients`를 사용한다.
- Migration/env/auth 변경은 없다.

## 실행 단계
- [x] Backend mapping 삭제 service와 facade export 추가
- [x] Backend DELETE view와 최소 view test 추가
- [x] Frontend DELETE API wrapper/hook/page handler 추가
- [x] 지정조합 뱃지 오른쪽 삭제 버튼 추가
- [x] Backend/frontend targeted checks 실행

## 검증
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py test api.drone.tests.DroneSopTargetRecipientTests.test_notification_target_mapping_endpoint_deletes_mapping api.drone.tests.DroneSopTargetRecipientTests.test_notification_target_mapping_endpoint_delete_returns_404_for_missing_mapping --keepdb`
- `npm run lint --workspace web -- src/features/line-dashboard/api/notificationRecipients.js src/features/line-dashboard/hooks/useLineSettings.js src/features/line-dashboard/components/LineSettingsPage.jsx src/features/line-dashboard/components/cards/NotificationTargetCard.jsx`
- `npm run agent:audit:ui`

## 위험과 대응
- 위험: DELETE body를 일부 환경에서 파싱하지 못할 수 있음.
- 대응: 기존 `_parse_json_body_or_error` 흐름을 그대로 사용해 `request.body` 기반 JSON 파싱을 유지한다.
- 위험: 삭제 후 선택된 target의 mapping 목록이 stale 상태로 남을 수 있음.
- 대응: backend 응답의 `target`으로 `notificationTargets`의 해당 target만 교체한다.

## 진행 기록
- 2026-05-20: 기존 생성 API만 있고 삭제 API가 없음을 확인해 backend/frontend 연결 범위로 계획 수립.
- 2026-05-20: DELETE service/view/API wrapper/hook/UI 삭제 버튼을 구현하고 targeted backend/frontend 검증을 통과.
