// 파일 경로: src/features/pm-spider/routes.jsx
// PM SPIDER 기능 라우트 정의입니다.
import { PmSpiderPage } from "./pages/PmSpiderPage"

export const pmSpiderRoutes = [
  {
    path: "spider/pm",
    element: <PmSpiderPage />,
  },
  {
    path: "pm_spider",
    element: <PmSpiderPage />,
  },
]
