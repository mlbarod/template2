# Web SPA 안내

`apps/web`은 React 19, React Router 7, Vite 6, Tailwind CSS 4로 만든 SPA입니다. 서버 데이터는 React Query로 관리하고, Zustand는 화면 상호작용 같은 UI 상태에만 사용합니다.

## 실행하기

저장소 루트에서:

```bash
npm run web:dev
```

`apps/web` 안에서 직접:

```bash
npm install
npm run dev
```

기본 주소는 `http://localhost:3000`입니다.

## 빌드와 린트

```bash
npm run web:build
npm run web:lint
```

`apps/web` 안에서 직접 실행할 수도 있습니다.

```bash
npm run build
npm run lint
npm run preview
```

## 환경 변수

개발 환경 변수는 `env/web.dev.env`에서 관리합니다.

| 변수 | 설명 |
| --- | --- |
| `VITE_BACKEND_URL` | 브라우저에서 호출할 Django API 주소 |
| `BACKEND_API_URL` | 컨테이너 내부 API 주소 |
| `VITE_ASSISTANT_API_URL` | Assistant 채팅 endpoint |
| `VITE_AIRFLOW_BASE_URL` | 브라우저용 Airflow 경로 |

## 코드 구조

| 경로 | 설명 |
| --- | --- |
| `src/components/ui` | shadcn/Radix 기반 UI primitive |
| `src/components/layout` | 전역 layout component |
| `src/components/common` | 여러 화면에서 쓰는 공통 component |
| `src/features/<feature>` | 기능별 page, component, hook, api, store |
| `src/lib` | API helper, auth facade, theme, query client |
| `src/routes/router.jsx` | 전역 route 조립 |

## 현재 feature

- `account`: 내 계정, 소속, 멤버/권한
- `appstore`: 내부 앱 목록/등록/댓글
- `assistant`: RAG 기반 채팅
- `auth`: 로그인, 온보딩, 소속 재확인
- `emails`: 메일함과 메일 처리
- `line-dashboard`: Drone SOP/라인 대시보드
- `timeline`: 설비/로그 타임라인
- `voc`: VOC 게시판
- `home`, `errors`, `teamstaff`: 공통 화면/보조 기능

## 개발 규칙 요약

- feature 외부 공개는 `src/features/<feature>/index.js` named export만 사용합니다.
- 다른 feature를 import할 때는 `@/features/<feature>` facade만 사용합니다.
- JSX 파일은 `.jsx`, 비 JSX 파일은 `.js`를 사용합니다.
- Tailwind와 design token을 우선 사용하고, 임의 HEX/inline style은 피합니다.
