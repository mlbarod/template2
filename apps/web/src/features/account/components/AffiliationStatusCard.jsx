import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"

export function AffiliationStatusCard({ affiliation, reconfirm }) {
  const needsReconfirm = Boolean(reconfirm?.requiresReconfirm)
  const predicted = reconfirm?.predictedUserSdwtProd || null

  return (
    <Card className="h-full">
      <CardHeader className="pb-1">
        <CardTitle>현재 소속</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <div className="overflow-hidden rounded-lg border">
          <table className="w-full table-fixed border-collapse">
            <thead className="bg-muted/40">
              <tr>
                <th className="border-b px-3 py-1.5 text-left text-xs font-medium text-muted-foreground">Department</th>
                <th className="border-b px-3 py-1.5 text-left text-xs font-medium text-muted-foreground">Line</th>
                <th className="border-b px-3 py-1.5 text-left text-xs font-medium text-muted-foreground">user_sdwt_prod</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td className="px-3 py-1.5 text-sm font-medium text-foreground">
                  {affiliation?.currentDepartment || "미지정"}
                </td>
                <td className="px-3 py-1.5 text-sm font-medium text-foreground">
                  {affiliation?.currentLine || "미지정"}
                </td>
                <td className="px-3 py-1.5 text-sm font-medium text-foreground">
                  {affiliation?.currentUserSdwtProd || "미지정"}
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <div className="flex flex-col gap-2">
          <div className="flex items-center gap-2">
            <span className="text-sm font-semibold text-foreground">재확인 상태</span>
            {needsReconfirm ? (
              <Badge variant="destructive">재확인 필요</Badge>
            ) : (
              <Badge variant="secondary">정상</Badge>
            )}
          </div>
          {predicted ? (
            <p className="text-sm text-muted-foreground">
              외부 예측 소속: <span className="font-medium text-foreground">{predicted}</span>
            </p>
          ) : (
            <p className="text-sm text-muted-foreground">외부 예측 소속 정보가 없습니다.</p>
          )}
        </div>
      </CardContent>
    </Card>
  )
}
