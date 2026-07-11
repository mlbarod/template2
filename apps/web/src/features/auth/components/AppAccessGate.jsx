import { Link } from "react-router-dom"
import { Home, ShieldX } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { getAppAccess } from "@/lib/access/appAccess"

import { useAuth } from "../hooks/useAuth"

export function AppAccessGate({ children, scopeKey, appName }) {
  const { user } = useAuth()
  const access = getAppAccess(user, scopeKey)

  if (!user) return null
  if (user.portal_access?.allowed && access?.allowed) return children

  return (
    <div className="flex h-full min-h-0 items-center justify-center overflow-y-auto bg-background px-6 py-10">
      <Card className="w-full max-w-md rounded-lg border bg-card shadow-sm" aria-labelledby="app-access-title">
        <CardHeader className="gap-3">
          <div className="flex size-10 items-center justify-center rounded-md border bg-muted text-muted-foreground">
            <ShieldX className="size-5" aria-hidden="true" />
          </div>
          <div className="space-y-2">
            <CardTitle id="app-access-title" className="text-base">
              {appName} 접근 권한이 없습니다
            </CardTitle>
            <CardDescription>앱 사용이 필요한 경우 권한 관리자에게 요청하세요.</CardDescription>
          </div>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground">
          권한 범위: <span className="font-medium text-foreground">{scopeKey}</span>
        </CardContent>
        <CardFooter>
          <Button asChild>
            <Link to="/">
              <Home className="size-4" />
              홈으로 이동
            </Link>
          </Button>
        </CardFooter>
      </Card>
    </div>
  )
}
