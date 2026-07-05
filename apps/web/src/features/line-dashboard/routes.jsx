// src/features/line-dashboard/routes.jsx
// 라인 대시보드에서 제공하는 페이지 라우트 정의를 모아둡니다.
import {
  LineDashboardEntryPage,
  LineDashboardDroneTargetAdminPage,
  LineDashboardHistoryPage,
  LineDashboardNotificationSettingsPage,
  LineDashboardOverviewPage,
  LineDashboardRecipientSettingsPage,
  LineDashboardSettingsPage,
  LineDashboardStatusPage,
} from "./pages"
import { LineDashboardShell } from "./components/LineDashboardShell"

export const lineDashboardRoutes = [
  {
    path: "ESOP_Dashboard",
    caseSensitive: false,
    element: <LineDashboardShell />,
    children: [
      {
        index: true,
        element: <LineDashboardEntryPage />,
      },
      {
        path: "status/:lineId",
        caseSensitive: false,
        element: <LineDashboardStatusPage />,
      },
      {
        path: "history/:lineId",
        caseSensitive: false,
        element: <LineDashboardHistoryPage />,
      },
      {
        path: "settings/notification/:lineId",
        caseSensitive: false,
        element: <LineDashboardNotificationSettingsPage />,
      },
      {
        path: "settings/recipients/:lineId",
        caseSensitive: false,
        element: <LineDashboardRecipientSettingsPage />,
      },
      {
        path: "settings/:lineId",
        caseSensitive: false,
        element: <LineDashboardSettingsPage />,
      },
      {
        path: "overview",
        caseSensitive: false,
        element: <LineDashboardOverviewPage />,
      },
      {
        path: "admin/drone-targets",
        caseSensitive: false,
        element: <LineDashboardDroneTargetAdminPage />,
      },
    ],
  },
]
