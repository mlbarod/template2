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

const ROLE_LABELS = {
  viewer: "뷰어",
  member: "멤버",
  manager: "관리자",
}

const ROLE_VARIANTS = {
  viewer: "secondary",
  member: "outline",
  manager: "default",
}

const SOURCE_LABELS = {
  self: "내 소속",
  grant: "부여됨",
  privileged: "관리자 전체",
  unknown: "기타",
}

function resolveRole(value) {
  return ROLE_LABELS[value] ? value : "viewer"
}

function formatDate(value) {
  if (!value) return "-"
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString("ko-KR")
}

export function MailboxAccessCard({ mailboxes }) {
  if (!mailboxes?.length) {
    return (
      <Card className="h-full">
        <CardHeader className="pb-2">
          <CardTitle>메일함 접근 현황</CardTitle>
          <CardDescription>접근 가능한 메일함의 상세 상태를 확인합니다.</CardDescription>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">접근 가능한 메일함이 없습니다.</p>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card className="h-full">
      <CardHeader className="pb-2">
        <CardTitle>메일함 접근 현황</CardTitle>
        <CardDescription>접근 가능한 메일함의 상세 상태를 확인합니다.</CardDescription>
      </CardHeader>
      <CardContent className="grid gap-3">
        <div className="max-h-48 min-h-0 overflow-y-auto rounded-lg border">
          <Table stickyHeader>
            <TableHeader>
              <TableRow>
                <TableHead>메일함</TableHead>
                <TableHead>접근 경로</TableHead>
                <TableHead>권한</TableHead>
                <TableHead>멤버 수</TableHead>
                <TableHead>내 메일 수</TableHead>
                <TableHead>부여 시각</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {mailboxes.map((mailbox) => {
                const role = resolveRole(mailbox.role)
                return (
                  <TableRow key={mailbox.userSdwtProd}>
                    <TableCell className="font-medium">{mailbox.userSdwtProd}</TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {SOURCE_LABELS[mailbox.accessSource] || mailbox.accessSource || "-"}
                    </TableCell>
                    <TableCell>
                      <Badge variant={ROLE_VARIANTS[role]}>{ROLE_LABELS[role]}</Badge>
                    </TableCell>
                    <TableCell className="text-sm">{mailbox.memberCount ?? "-"}</TableCell>
                    <TableCell className="text-sm">{mailbox.myEmailCount ?? "-"}</TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {formatDate(mailbox.grantedAt || mailbox.myGrantedAt)}
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
