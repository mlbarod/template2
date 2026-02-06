import { Outlet } from "react-router-dom"

import HomeNavbar from "./Navbar"
import { navigationItems } from "../utils/constants"

export function GlobalNavbarShell({ children }) {
  return (
    <div className="h-screen flex flex-col bg-background">
      <header className="h-14 shrink-0 border-b bg-background">
        <div className="h-full">
          <HomeNavbar navigationItems={navigationItems} />
        </div>
      </header>
      <main className="flex-1 min-h-0 overflow-hidden pt-2">
        {children ?? <Outlet />}
      </main>
    </div>
  )
}
