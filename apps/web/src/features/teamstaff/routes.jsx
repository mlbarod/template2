// /src/features/teamstaff/routes.jsx
// 모델 기능의 라우트 정의를 묶어둡니다.
import { HomeShell } from "@/features/home"
import TeamStaffPage from "./pages/TeamStaffPage"

export const teamstaffRoutes = [
  {
    element: <HomeShell />,
    children: [
      {
        path: "teamstaff",
        element: <TeamStaffPage />,
      },
    ],
  },
]
