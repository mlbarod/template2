# ExecPlan: ESOP ChangeType Legend

## 목표
- ESOP 로그 legend와 타임라인 색상을 고정 ChangeType 목록 기준으로 표시한다.

## 현재 상태
- ESOP legend는 `ESOP` 단일 항목으로 고정되어 있다.
- ESOP 타임라인 item은 `eventType` 값을 받지만 색상은 기본 ESOP 색상 하나만 사용한다.
- ESOP `eventType`은 백엔드에서 `drone_sop.sample_type` 값을 내려준다.

## 범위
- `apps/web/src/features/observer` 내부의 ESOP legend, 색상 매핑, legend layout만 수정한다.
- API 응답, DB schema, observer backend selector는 변경하지 않는다.

## 설계
- 사용자가 제공한 빈도순 ChangeType 목록을 고정 legend 순서로 사용한다.
- `eventType`과 ChangeType class 매핑을 공유 유틸로 분리한다.
- 긴 ESOP legend가 헤더 밖으로 넘치지 않도록 legend 줄바꿈을 허용한다.
- public facade, migration, env, auth 영향은 없다.

## 실행 단계
- [x] ESOP ChangeType 고정 목록과 class map 추가
- [x] ESOP legend와 `observerMeta` 색상 매핑 연결
- [x] ESOP 색상 CSS class 추가
- [x] legend 줄바꿈 허용
- [x] UI audit 실행

## 검증
- `npm run agent:audit:ui`
- 기대 결과: UI consistency audit 통과

## 위험과 대응
- 위험: 마지막 `SKEw_ANY` 값의 대소문자가 실제 데이터와 다를 수 있다.
- 대응: legend는 `SKEW_ANY`로 표시하고, 데이터 매칭은 `SKEW_ANY`와 `SKEw_ANY`를 같은 class로 처리한다.

## 진행 기록
- 2026-06-22: ESOP ChangeType legend 하드코딩 구현 계획 작성.
- 2026-06-22: ESOP ChangeType 고정 목록, legend, 색상 class, 줄바꿈 처리를 추가.
- 2026-06-22: `npm run agent:audit:ui`, `npm run agent:audit:web-boundary` 통과.
