import { Navigate } from "react-router-dom"

import { AccountSettingsShell } from "./components/AccountSettingsShell"
import AccountPage from "./pages/AccountPage"
import MembersPage from "./pages/MembersPage"
import PermissionsPage from "./pages/PermissionsPage"
import SettingsPage from "./pages/SettingsPage"

export const accountRoutes = [
  {
    path: "settings",
    element: <AccountSettingsShell />,
    children: [
      {
        element: <SettingsPage />,
        children: [
          {
            index: true,
            element: <Navigate to="account" replace />,
          },
          {
            path: "account",
            element: <AccountPage />,
          },
          {
            path: "members",
            element: <MembersPage />,
          },
          {
            path: "permissions",
            element: <PermissionsPage />,
          },
        ],
      },
    ],
  },
]
