# ExecPlan: CTTTM 순차 요약 스트리밍

## 목표
- CTTTM 상세에서 `핵심요약` 스트리밍이 끝난 뒤 `Summary` 스트리밍이 시작되도록 한다.

## 현재 상태
- `CtttmDetail.jsx`에서 두 `Field`가 모두 `streaming={true}`로 렌더링된다.
- `Field.jsx`는 `StreamingText`에 진행 콜백만 전달한다.
- `StreamingText.jsx`는 텍스트 완료 시점을 외부에 알리지 않는다.

## 범위
- 수정 대상은 Observer 상세의 스트리밍 표시 컴포넌트에 한정한다.
- API, 데이터 변환, 라우팅, 공개 facade는 변경하지 않는다.

## 설계
- `StreamingText`에 `active`와 `onComplete` props를 추가한다.
- `Field`가 스트리밍 시작/완료 props를 그대로 전달한다.
- `CtttmDetail`은 `핵심요약` 완료 상태를 들고 있다가 완료 후 `Summary`의 스트리밍을 활성화한다.

## 실행 단계
- [x] `StreamingText`에 시작 제어와 완료 콜백을 추가한다.
- [x] `Field`에 전달 props를 추가한다.
- [x] `CtttmDetail`에서 `Summary` 스트리밍을 핵심요약 완료 후 활성화한다.

## 검증
- `git diff --check`
- `scripts/agent/check_ui_consistency.sh`

## 위험과 대응
- 위험: 캐시된 텍스트가 즉시 표시될 때 완료 콜백이 누락될 수 있다.
- 대응: 완료 상태를 `currentIndex >= text.length` 기준으로 감지한다.

## 진행 기록
- 2026-07-06: 순차 스트리밍 적용 범위와 완료 콜백 설계를 정리했다.
- 2026-07-06: `핵심요약` 완료 키가 현재 로그와 일치할 때만 `Summary` 스트리밍을 시작하도록 구현했다.
- 2026-07-06: `git diff --check`와 `npm run lint`를 통과했다. UI audit은 기존 `l3-spider` 후보로 실패했다.
