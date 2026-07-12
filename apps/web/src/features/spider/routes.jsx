import { DefectSpiderExternalPage } from "./pages/DefectSpiderExternalPage"
import { SpiderHomePage } from "./pages/SpiderHomePage"

export const spiderRoutes = [
  {
    path: "spider",
    element: <SpiderHomePage />,
  },
  {
    path: "spider/defect",
    element: <DefectSpiderExternalPage />,
  },
]
