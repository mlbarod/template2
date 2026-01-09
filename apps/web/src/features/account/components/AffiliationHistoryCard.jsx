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

const STATUS_LABELS = {
  PENDING: { label: "대기", variant: "secondary" },
  APPROVED: { label: "승인", variant: "default" },
  REJECTED: { label: "거절", variant: "destructive" },
  SUPERSEDED: { label: "취소(대체됨)", variant: "outline" },
}

function formatDate(value) {
  if (!value) return "-"
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString("ko-KR")
}

export function AffiliationHistoryCard({ history }) {
  if (!history?.length) {
    return (
      <Card className="h-full">
        <CardHeader className="pb-2">
          <CardTitle>승인/변경 히스토리</CardTitle>
          <CardDescription>소속 변경 신청과 승인 결과를 확인합니다.</CardDescription>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">변경 히스토리가 없습니다.</p>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card className="h-full">
      <CardHeader className="pb-2">
        <CardTitle>승인/변경 히스토리</CardTitle>
        <CardDescription>소속 변경 신청과 승인 결과를 확인합니다.</CardDescription>
      </CardHeader>
      <CardContent className="grid gap-3">
        <div className="rounded-lg border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>상태</TableHead>
                <TableHead>변경</TableHead>
                <TableHead>조직</TableHead>
              <TableHead>적용 시점</TableHead>
              <TableHead>요청 시점</TableHead>
              <TableHead>승인자</TableHead>
              <TableHead>거절 사유</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {history.map((item) => {
                const status = STATUS_LABELS[item.status] || {
                  label: item.status || "미지정",
                  variant: "outline",
                }
                return (
                  <TableRow key={item.id}>
                    <TableCell>
                      <Badge variant={status.variant}>{status.label}</Badge>
                    </TableCell>
                    <TableCell className="text-sm">
                      {(item.fromUserSdwtProd || "-") + " → " + (item.toUserSdwtProd || "-")}
                    </TableCell>
                    <TableCell className="text-sm">
                      {(item.department || "미지정") + " / " + (item.line || "미지정")}
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {formatDate(item.effectiveFrom)}
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {formatDate(item.requestedAt)}
                    </TableCell>
                    <TableCell className="text-sm">
                      {item.approvedBy?.username || "-"}
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {item.rejectionReason || "-"}
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
