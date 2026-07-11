import { Navigate } from "react-router-dom"

import { L0SpiderShell } from "./components/L0SpiderShell"
import { L0SpiderDashboardPage } from "./pages/L0SpiderDashboardPage"
import { L0SpiderExternalPage } from "./pages/L0SpiderExternalPage"
import { SpiderFeaturePage } from "./pages/SpiderFeaturePage"

const l0SpiderChildren = [
  {
    index: true,
    element: <Navigate to="/spider" replace />,
  },
  {
    path: "self-equipment",
    element: <L0SpiderDashboardPage />,
  },
  {
    path: "matching-anomaly",
    element: <SpiderFeaturePage type="matching" />,
  },
  {
    path: "common-anomaly",
    element: <SpiderFeaturePage type="common" />,
  },
  {
    path: "history",
    element: <SpiderFeaturePage type="history" />,
  },
  {
    path: "manual",
    element: <SpiderFeaturePage type="manual" />,
  },
  {
    path: "fdc-hard-limit",
    element: <SpiderFeaturePage type="hardSpec" />,
  },
  {
    path: "yield-hard-limit",
    element: <SpiderFeaturePage type="yieldSpec" />,
  },
  {
    path: "recipients",
    element: <SpiderFeaturePage type="recipients" />,
  },
  {
    path: "defect-spider",
    element: <SpiderFeaturePage type="defect" />,
  },
  {
    path: "l1-spider",
    element: <SpiderFeaturePage type="l1" />,
  },
  {
    path: "l3-spider",
    element: <SpiderFeaturePage type="l3" />,
  },
]

export const l0SpiderRoutes = [
  {
    path: "spider/l0",
    element: <L0SpiderExternalPage />,
  },
  {
    path: "l0_spider",
    element: <L0SpiderShell />,
    children: l0SpiderChildren,
  },
  {
    path: "fdc_trend",
    element: <L0SpiderShell />,
    children: l0SpiderChildren,
  },
]
