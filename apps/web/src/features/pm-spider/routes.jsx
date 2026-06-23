// 파일 경로: src/features/pm-spider/routes.jsx
// PM SPIDER 기능 라우트 정의입니다.
import { Navigate } from "react-router-dom"

import { PmSpiderPage } from "./pages/PmSpiderPage"

export const pmSpiderRoutes = [
  {
    path: "pm_spider",
    element: <PmSpiderPage />,
  },
  {
    path: "pm-comparison",
    element: <Navigate to="/pm_spider" replace />,
  },
]
