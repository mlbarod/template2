import { PortalHomeShell } from "@/components/layout"

import HomePage from "./pages/HomePage"
import ReactLogoBlankPage from "./pages/ReactLogoBlankPage"

export const homeRoutes = [
  {
    element: <PortalHomeShell />,
    children: [
      {
        index: true,
        element: <HomePage />,
      },
      {
        path: "react-logo-preview",
        element: <ReactLogoBlankPage />,
      },
    ],
  },
]
