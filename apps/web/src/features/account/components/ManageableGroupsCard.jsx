import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/common"

import {
  ACCESS_ROLE_LABELS,
  ACCESS_ROLE_VARIANTS,
  buildManageableGroupRows,
  countManageableGroupMembers,
  formatAccountDateValue,
  resolveAccessRole,
} from "../utils/accountOverview"

export function ManageableGroupsCard({ groups }) {
  const groupRows = buildManageableGroupRows(groups || [])
  const memberCount = countManageableGroupMembers(groups || [])

  if (!groups?.length) {
    return (
      <Card className="h-full min-h-0 gap-0 overflow-hidden py-0">
        <CardHeader className="shrink-0 border-b px-5 py-4">
          <CardTitle>관리 가능한 그룹</CardTitle>
          <CardDescription>현재 사용자가 관리 가능한 user_sdwt_prod 목록입니다.</CardDescription>
        </CardHeader>
        <CardContent className="min-h-0 flex-1 overflow-y-auto p-5">
          <p className="text-sm text-muted-foreground">관리 가능한 그룹이 없습니다.</p>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card className="h-full min-h-0 gap-0 overflow-hidden py-0">
      <CardHeader className="shrink-0 border-b px-5 py-4">
        <div className="flex items-start justify-between gap-3">
          <div className="space-y-1">
            <CardTitle>관리 가능한 그룹</CardTitle>
            <CardDescription>그룹별 멤버와 권한 상태를 확인합니다.</CardDescription>
          </div>
          <Badge variant="secondary">{groups.length}개 그룹</Badge>
        </div>
      </CardHeader>
      <CardContent className="grid min-h-0 flex-1 grid-rows-[70px_minmax(0,1fr)] gap-4 overflow-y-auto p-5">
        <div className="grid self-start gap-3 sm:grid-cols-2">
          <div className="rounded-lg border bg-muted/30 p-3">
            <p className="text-xs text-muted-foreground">관리 그룹</p>
            <p className="mt-1 text-lg font-semibold">{groups.length.toLocaleString("ko-KR")}</p>
          </div>
          <div className="rounded-lg border bg-muted/30 p-3">
            <p className="text-xs text-muted-foreground">등록 멤버</p>
            <p className="mt-1 text-lg font-semibold">{memberCount.toLocaleString("ko-KR")}</p>
          </div>
        </div>
        <div className="rounded-lg border">
          <Table stickyHeader>
            <TableHeader>
              <TableRow>
                <TableHead>그룹</TableHead>
                <TableHead>사용자</TableHead>
                <TableHead>권한</TableHead>
                <TableHead>부여 시각</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {groupRows.map(({ group, member }) => {
                if (!member) {
                  return (
                    <TableRow key={`${group.userSdwtProd}-empty`}>
                      <TableCell className="font-medium">{group.userSdwtProd}</TableCell>
                      <TableCell colSpan={3} className="text-sm text-muted-foreground">
                        멤버가 없습니다.
                      </TableCell>
                    </TableRow>
                  )
                }

                const username = member.username || "미지정"
                const knoxId = member.knoxId || member.knox_id
                const name = (member.name || "").trim()
                const detail = name && knoxId ? `${name} (${knoxId})` : name || knoxId || ""
                const role = resolveAccessRole(member.role)

                return (
                  <TableRow key={`${group.userSdwtProd}-${member.userId}`}>
                    <TableCell className="font-medium">{group.userSdwtProd}</TableCell>
                    <TableCell>
                      <div className="flex min-w-0 flex-col">
                        <span className="truncate font-medium">{username}</span>
                        {detail ? <span className="truncate text-xs text-muted-foreground">{detail}</span> : null}
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge variant={ACCESS_ROLE_VARIANTS[role]}>{ACCESS_ROLE_LABELS[role]}</Badge>
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {formatAccountDateValue(member.grantedAt)}
                    </TableCell>
                  </TableRow>
                )
              })}
            </TableBody>
          </Table>
        </div>
      </CardContent>
    </Card>
  )
}
