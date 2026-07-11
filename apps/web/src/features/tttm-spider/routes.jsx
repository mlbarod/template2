// 파일 경로: src/features/tttm-spider/routes.jsx
// TTTM Spider 임베드 라우트 정의입니다.
import { TttmSpiderPage } from "./pages/TttmSpiderPage"

export const tttmSpiderRoutes = [
  {
    path: "spider/tttm",
    element: <TttmSpiderPage />,
  },
  {
    path: "tttm_spider",
    element: <TttmSpiderPage />,
  },
]
