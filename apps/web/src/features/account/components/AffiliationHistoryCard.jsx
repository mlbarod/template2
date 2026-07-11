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

import { formatAccountDateValue, getRequestStatus } from "../utils/accountOverview"

export function AffiliationHistoryCard({ history }) {
  if (!history?.length) {
    return (
      <Card className="h-full min-h-0 gap-0 overflow-hidden py-0">
        <CardHeader className="shrink-0 border-b px-5 py-4">
          <CardTitle>승인/변경 히스토리</CardTitle>
          <CardDescription>소속 변경 신청과 승인 결과를 시간순으로 추적합니다.</CardDescription>
        </CardHeader>
        <CardContent className="min-h-0 flex-1 overflow-y-auto p-5">
          <p className="text-sm text-muted-foreground">변경 히스토리가 없습니다.</p>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card className="h-full min-h-0 gap-0 overflow-hidden py-0">
      <CardHeader className="shrink-0 border-b px-5 py-4">
        <div className="flex items-start justify-between gap-3">
          <div className="space-y-1">
            <CardTitle>승인/변경 히스토리</CardTitle>
            <CardDescription>소속 변경 신청과 승인 결과를 시간순으로 추적합니다.</CardDescription>
          </div>
          <Badge variant="outline">{history.length.toLocaleString("ko-KR")}건</Badge>
        </div>
      </CardHeader>
      <CardContent className="min-h-0 flex-1 overflow-y-auto p-5">
        <div className="rounded-lg border">
          <Table stickyHeader>
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
                const status = getRequestStatus(item.status)
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
                      {formatAccountDateValue(item.effectiveFrom)}
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {formatAccountDateValue(item.requestedAt)}
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
