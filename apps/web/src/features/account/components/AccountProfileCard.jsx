import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"

const ROLE_LABELS = {
  admin: "Admin",
  manager: "Manager",
  viewer: "Viewer",
}

export function AccountProfileCard({ profile, affiliation, reconfirm }) {
  const roleKey = (profile?.role || "").toLowerCase()
  const roleLabel = ROLE_LABELS[roleKey] || profile?.role || "미지정"
  const needsReconfirm = Boolean(reconfirm?.requiresReconfirm)
  const reconfirmLabel = needsReconfirm ? "재확인 필요" : "정상"
  const lineValue = affiliation?.currentLine || "미지정"
  const statusBadges = [
    profile?.isSuperuser ? "슈퍼유저" : null,
    profile?.isStaff ? "스태프" : null,
  ].filter(Boolean)

  return (
    <Card className="h-full">
      <CardHeader className="pb-1">
        <CardTitle>사용자 기본 정보</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <div className="overflow-hidden rounded-lg border">
          <table className="w-full table-fixed border-collapse">
            <thead className="bg-muted/40">
              <tr>
                <th className="border-b px-3 py-1.5 text-center text-xs font-medium text-muted-foreground">Username</th>
                <th className="border-b px-3 py-1.5 text-center text-xs font-medium text-muted-foreground">Knox ID</th>
                <th className="border-b px-3 py-1.5 text-center text-xs font-medium text-muted-foreground">Role</th>
                <th className="border-b px-3 py-1.5 text-center text-xs font-medium text-muted-foreground">user_sdwt_prod</th>
                <th className="border-b px-3 py-1.5 text-center text-xs font-medium text-muted-foreground">Line</th>
                <th className="border-b px-3 py-1.5 text-center text-xs font-medium text-muted-foreground">재확인 상태</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td className="px-3 py-1.5 text-center text-sm font-medium text-foreground">{profile?.username || "미지정"}</td>
                <td className="px-3 py-1.5 text-center text-sm font-medium text-foreground">{profile?.knoxId || "미지정"}</td>
                <td className="px-3 py-1.5 text-center text-sm font-medium text-foreground">{roleLabel}</td>
                <td className="px-3 py-1.5 text-center text-sm font-medium text-foreground">{profile?.userSdwtProd || "미지정"}</td>
                <td className="px-3 py-1.5 text-center text-sm font-medium text-foreground">{lineValue}</td>
                <td className="px-3 py-1.5 text-center">
                  <Badge variant={needsReconfirm ? "destructive" : "secondary"}>{reconfirmLabel}</Badge>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        {statusBadges.length ? (
          <div className="flex flex-wrap gap-2">
            {statusBadges.map((label) => (
              <Badge key={label} variant="secondary">
                {label}
              </Badge>
            ))}
          </div>
        ) : null}
      </CardContent>
    </Card>
  )
}
