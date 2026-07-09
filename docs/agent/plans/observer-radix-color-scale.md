# ExecPlan: Observer Radix Color Scale

## 목표
- Observer 타임라인/범례 색상을 Radix Colors scale 기반으로 바꾼다.
- 개발자가 로그 타입별 scale class 하나를 바꾸면 배경, 테두리, 텍스트, dark mode 색상이 함께 따라가게 한다.

## 현재 상태
- `observer.css`는 로그별 `bg/border/text` 값을 직접 지정한다.
- `observerMeta.js`, `observerLegends.js`, `esopChangeTypes.js`가 `observer-color-*` 클래스명을 공급한다.
- `@radix-ui/colors` 의존성이 없어 추가가 필요하다.

## 범위
- 수정: Observer 색상 CSS, Observer 색상 class 매핑, web package 의존성/lock.
- 제외: API, DB, 라우팅, Observer 데이터 처리 로직.

## 설계
- Radix Colors CSS scale을 import한다.
- `observer-scale-*` class가 `--observer-item-bg-color`, `--observer-item-border-color`, `--observer-item-text-color`를 설정한다.
- 기존 `observer-color-*` class는 식별/호환용으로 유지하고, scale class를 함께 부여한다.
- public facade, migration, env, auth 영향은 없다.

## 실행 단계
- [x] `@radix-ui/colors` 의존성을 추가한다.
- [x] Observer CSS에 Radix scale import와 scale class를 추가한다.
- [x] Observer 로그/범례 class 매핑에 scale class를 함께 부여한다.
- [x] UI/boundary/build 검증을 실행한다.

## 검증
- `npm run agent:audit:ui`
- `npm run agent:audit:web-boundary`
- `npm run web:build`
- `git diff --check`

## 위험과 대응
- 위험: CSS import 순서가 dark mode 변수 적용을 깨뜨릴 수 있다.
- 대응: Radix light/dark CSS를 Observer CSS 상단에서 함께 import하고 `.dark` selector 기반 동작을 사용한다.

## 진행 기록
- 2026-07-09: Radix Colors scale class 기반 구조로 변경하기로 결정했다.
- 2026-07-09: `observer-scale-*` 클래스와 중앙 `OBSERVER_COLOR_CLASSES` 매핑을 추가하고 검증을 통과했다.
