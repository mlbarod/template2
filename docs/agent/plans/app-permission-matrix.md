# ExecPlan: 앱 권한 매트릭스 관리 UI

## 목표
- 관리자가 사용자 행과 앱 열로 구성된 매트릭스에서 앱별 수동 권한을 빠르게 조회하고 변경할 수 있게 한다.

## 현재 상태
- `AccessScope`, `UserAccess`, 사용자별 scope 결정 API와 감사 로그가 이미 존재한다.
- 권한 관리 화면은 portal scope 한 개만 조회하며 앱 scope 선택 UI가 없다.
- 앱 scope 12개를 등록하는 권한 데이터 migration이 추가된 상태다.

## 범위
- 활성 app scope와 페이지 사용자별 최종 권한을 일괄 반환하는 관리자 API를 추가한다.
- 권한 관리 화면에 사용자 × 앱 권한 매트릭스 탭을 추가한다.
- 셀 변경은 기존 사용자별 권한 결정 API를 재사용한다.
- 앱 scope seed의 기존 키 충돌과 위험한 역방향 삭제를 보완한다.
- 앱 route/API 접근 강제는 수정하지 않는다.

## 설계
- 조회 API: `GET /api/v1/account/access/matrix`
- 응답은 `scopes`, `results[{user, accesses}]`, `pagination`으로 구성한다.
- 사용자 검색과 부서 필터 및 서버 페이지네이션을 지원한다.
- 각 셀은 `자동/미지정`, `허용`, `차단` 상태를 제공한다.
- `자동/미지정`은 `reset_to_policy`, 허용은 `grant`, 차단은 `revoke`로 기존 서비스에 전달한다.
- 매트릭스 조회는 페이지 사용자, 앱 scope, 정책, 명시 권한을 각각 일괄 조회해 N+1을 방지한다.

## 실행 단계
- [x] matrix selector/service/view/URL 구현
- [x] API 및 권한 변경 테스트 추가
- [x] 프론트엔드 API/query hook 연결
- [x] 앱 권한 매트릭스 UI와 권한 페이지 탭 추가
- [x] migration 안전성 보완
- [x] 백엔드·프론트엔드 검증

## 검증
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py makemigrations --check`
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py test --keepdb api.account`
- `npm --prefix apps/web run lint`
- `npm --prefix apps/web run build`
- `npm run agent:audit:api-boundary`
- `scripts/agent/check_frontend_boundaries.sh`
- `scripts/agent/check_ui_consistency.sh`

## 위험과 대응
- 위험: 넓은 앱 열로 화면이 밀릴 수 있다.
- 대응: 테이블 내부 가로 스크롤과 sticky 사용자 열을 사용한다.
- 위험: 자동 정책 권한을 수동 권한으로 오인할 수 있다.
- 대응: 자동/미지정 상태와 최종 권한 정보를 함께 표시하고 reset 동작을 제공한다.
- 위험: 다수 셀 변경 중 중복 요청이 발생할 수 있다.
- 대응: 변경 중인 셀만 비활성화하고 성공 후 matrix와 감사 로그 query를 갱신한다.

## 진행 기록
- 2026-07-10: 기존 권한 계약을 재사용하는 일괄 조회 API와 매트릭스 UI 설계를 확정했다.
- 2026-07-10: matrix API/UI와 앱 scope 수동 변경 테스트를 추가하고 로컬 DB에 권한 migration을 적용했다.
- 2026-07-10: account 테스트 113건, 변경 파일 ESLint, production build, migration check, backend boundary audit를 통과했다. 전체 lint와 기존 frontend/UI 감사에는 요청 범위 밖 선행 이슈가 남아 있다.
- 2026-07-11: 실제 enforcement가 allowed만 검사하는 계약에 맞춰 앱 역할 선택을 제거하고 자동/허용/차단으로 단순화했다.
