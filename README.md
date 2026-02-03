# 🧭 agents.md — Ultra-Optimized Constitution for LLM Agents
aaa
### (Strict, Unambiguous, Machine-Executable Rules)

이 문서는 LLM 에이전트가 반드시 따라야 하는 **절대 규칙(Constitution)**을 정의한다.
모든 규칙은 모호함 없이 실행 가능해야 하며, 생성되는 아키텍처가 항상 일관되고 재현 가능하도록 한다.

LLM 에이전트는 **이 문서의 모든 규칙을 100% 준수해야 한다.**
조금이라도 불확실한 경우, 에이전트는 반드시 인간에게 질문해야 한다.

---

# 1. Global Execution Rules

## 1-1. Deterministic Behavior

LLM 에이전트는 반드시:

* 모든 규칙을 정확히 따르고, 추측이나 창작을 하지 않는다.
* 폴더 경로, 컴포넌트 구조, 네이밍을 일관되게 유지한다.
* 명시되지 않은 패턴을 새로 발명하지 않는다.
* 세부사항이 불분명하면 무조건 질문한다.

## 1-2. Output Format Rules

* 코드는 항상 문법적으로 유효해야 한다.
* 파일 경로는 반드시 `/` 를 사용한다.
* import 경로는 실제로 존재해야 한다.
* 컴포넌트: PascalCase
* 훅(hook): camelCase
* 유틸 함수: camelCase
* Feature export는 항상 해당 feature의 `index.js`를 통한다.

---

# 2. Architectural Rules (LLM-Strict)

## 2-1. Vertical Slice Isolation

모든 기능은 완전한 Vertical Slice로 구성해야 한다.

### Feature Path

```
apps/web/src/features/<feature>
```

### Allowed Subfolders

```
pages/
components/
hooks/
api/
store/
utils/
routes.jsx
index.js
```

### MUST obey

* 새로운 폴더는 생성 불가.
* 2단계보다 깊은 폴더 구조는 금지.
* 다른 feature 내부 경로로 import 금지.

### Allowed Imports

* `apps/web/src/components/ui/*`
* `apps/web/src/components/layout/*`
* `apps/web/src/components/common/*`
* `apps/web/src/lib/*`
* `apps/web/src/features/<otherFeature>/index.js` (최상위만)

그 외 import는 **INVALID**.

---

# 3. UI Stack Rules

## 3-1. Immutable UI Layer

LLM 에이전트는 다음 경로를 절대 수정할 수 없다:

```
apps/web/src/components/ui/**/*
```

새로운 UI primitive는 반드시 shadcn CLI를 사용해 추가한다.

## 3-2. UI Assembly Hierarchy

UI는 반드시 아래 계층 구조를 따른다.

1. UI primitives (`components/ui/*`)
2. Layout components (`components/layout/*`)
3. Common shared components (`components/common/*`)
4. Feature-specific UI (`features/<feature>/components/*`)

이 계층 구조를 바꾸는 것은 금지한다.

---

# 4. Routing Rules

## 4-1. Feature Route Export

각 feature는 반드시 `routes.jsx`를 포함하고 route 설정을 export해야 한다.

## 4-2. Global Routes

전역 라우팅은 오직:

```
apps/web/src/routes/*
```

에만 존재한다.

## 4-3. No Business Logic in Routes

Routes는 다음만 가능:

* 구조 정의
* element 지정
* param validation
* redirect

Routes 내부에 다음은 **절대 금지**:

* 비즈니스 로직
* 데이터 로직
* UI 상태 계산

---

# 5. State & Data Rules

## 5-1. React Query

React Query는 유일한 서버 데이터 출처이다.

LLM MUST:

* 배열 기반 Query Key 사용
* 중복된 키 사용 금지
* 최소 단위 invalidation
* Zustand에 서버 데이터 저장 금지

## 5-2. Zustand

Zustand는 다음 목적에만 사용 가능:

* UI 상태
* Interaction Flow
* Multi-step form
* 임시 공유 상태

Zustand에 다음은 금지:

* 서버 데이터
* Redux 스타일 mega-store
* 전역 비즈니스 상태

Store path 규칙:

```
apps/web/src/features/<feature>/store/useSomethingStore.js
```

---

# 6. Coding Rules

## 6-1. Naming

* Components → PascalCase
* Hooks → camelCase
* Utilities → camelCase
* Zustand store → useSomethingStore
* Pages → PascalCase
* API modules → camelCase

## 6-2. Styling

LLM MUST:

* Tailwind classnames 사용
* design tokens (`text-primary`, `bg-muted` 등)만 사용
* dark mode는 `dark:` prefix

LLM MUST NOT:

* 임의의 HEX 값 사용
* inline 스타일 사용 (필요 시 예외)

---

# 7. React 19 Rules

LLM MUST NOT:

* 불필요한 useMemo
* 불필요한 useCallback
* 불필요한 React.memo

Allowed only when:

* 무거운 계산이 존재함
* 라이브러리가 stable identity 요구

---

# 8. Backend / Django Rules

LLM MUST:

* API prefix는 `/api/v1/<feature>`
* 앱 간 모델 import 금지
* 도메인 로직은 service 계층에 존재해야 함
* 모든 timestamp는 UTC

---

# 9. File Generation Rules

새 파일 생성 시:

1. 전체 경로 출력
2. 파일 내용 전체 출력
3. import 유효성 보장
4. 아키텍처 규칙 준수
5. 일관된 naming 적용

기존 파일 수정 시:

* 구조 보존
* export 유지
* 요청 범위 외 변경 금지

---

# 10. LLM Error Handling Rules

LLM MUST ask for clarification when:

* 폴더명 모호
* 파일 위치 불명확
* API schema 없음
* 복수 해석 가능

LLM MUST NOT guess.

---

# 11. Layout Rules (Strict for All Features)

## 11-1. Layout Philosophy

레이아웃은 다음 두 원칙을 따른다:

1. 바깥 컨테이너는 고정 높이 또는 구조적 Flex/Grid를 제공한다.
2. **스크롤은 한 축에서 단 하나의 요소에서만 발생한다.**

스크롤이 여러 곳에서 동시에 발생하면 INVALID.

---

## 11-2. Global Page Skeleton Rule

모든 페이지는 다음 기본 골격을 따라야 한다:

```tsx
<div class="h-screen flex flex-col">
  <header class="h-16 shrink-0"> ... </header>

  <main class="flex-1 min-h-0 overflow-hidden">
    {children}
  </main>
</div>
```

LLM MUST:

* `h-screen flex flex-col` 사용
* Header는 고정 높이 + `shrink-0`
* Content는 `flex-1 min-h-0 overflow-hidden`
* 스크롤은 main 내부에서만 발생

---

## 11-3. Flex vs Grid Rules

### Flex MUST be used for:

* 단방향 정렬 (row/col)
* 버튼·툴바 정렬
* 가운데 정렬
* 작은 UI 구성

### Grid MUST be used for:

* 2~3개 영역 분리 (리스트/상세)
* 상단 고정 + 아래 스크롤 분리
* 고정/비율 row 구성

---

## 11-4. Scroll Rules

### Rule A — 스크롤은 한 요소에서만 발생

```tsx
<div class="min-h-0 overflow-y-auto">...</div>
```

### Rule B — 스크롤 부모는 반드시 min-h-0

### Rule C — 위는 고정, 아래는 스크롤 패턴은 아래만 허용

```tsx
<div class="grid h-full min-h-0 grid-rows-[auto,1fr]">
  <div>고정영역</div>
  <div class="min-h-0 overflow-y-auto">스크롤영역</div>
</div>
```

---

## 11-5. Two-Pane Layout Rule

(왼쪽 리스트 + 오른쪽 상세)

```tsx
<div class="grid flex-1 min-h-0 gap-4 md:grid-cols-2">
  <div class="grid min-h-0 grid-rows-[auto,1fr] gap-2">
    <div class="h-[고정높이 또는 auto] overflow-hidden">{filters}</div>
    <div class="min-h-0 overflow-y-auto">{list}</div>
  </div>

  <div class="min-h-0 overflow-y-auto">{detail}</div>
</div>
```

LLM MUST:

* 필터는 고정 or auto 높이
* 리스트는 반드시 단독 스크롤
* 상세뷰도 단독 스크롤

---

## 11-6. Padding Responsibility Rules (상·하위 패딩 규칙)

### Layout(상위 컨테이너)의 책임

* 페이지 전체 좌우 padding (`px-4 md:px-6`)
* 섹션 간 gap
* 전체 스크롤 구조
* 작업 공간 여백 (work area padding)

### Component(하위 컴포넌트)의 책임

* 자체 내부 콘텐츠 padding (`p-4`, `p-3` 등)
* 컴포넌트 내부 spacing

### STRICT RULES

LLM MUST NOT:

* 상위가 하위 내부 padding을 조절하게 만들지 말 것
* 하위가 페이지 전체 padding을 설정하지 말 것
* 여러 레벨에서 padding이 중복되게 만들지 말 것

**상위는 외부 여백, 하위는 내부 여백.**
섞이면 INVALID.

---

## 11-7. Spacing Rules

* Page padding: `p-4 md:p-6`
* Section gaps: `gap-4`
* Internal component spacing: `gap-2` or `gap-3`
* 대형 레이아웃 구분: `gap-6`

임의 spacing 값 사용은 금지.

---

## 11-8. Layout Componentization Rule

레이아웃 패턴이 2회 이상 반복되면, LLM MUST 생성:

```
apps/web/src/components/layout/<LayoutName>.jsx
```

Feature 내부에는 레이아웃 컴포넌트를 절대 생성하지 않는다.

---

## 11-9. Layout & Feature Boundary

LLM MUST:

* 레이아웃 → `components/layout/*`
* 공용 UI → `components/common/*`
* 개별 feature UI → `features/<feature>/components/*`

레이아웃과 feature UI가 결합되면 INVALID.

---

# ✔ End of Ultra-Optimized LLM Constitution

이 문서는 프로젝트 전체의 헌법이며,
LLM은 코드를 생성하거나 수정할 때 **항상 이 규칙을 기반으로 수행해야 한다.**
