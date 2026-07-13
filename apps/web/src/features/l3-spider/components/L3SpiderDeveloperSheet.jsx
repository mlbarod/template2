import { useState } from "react"
import { AlertTriangle, CheckCircle2, Loader2, RefreshCw, Wrench } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"

import { useL3SpiderUnmappedLineRules } from "../hooks/useL3SpiderQueries"

export function L3SpiderDeveloperSheet() {
  const [open, setOpen] = useState(false)
  const query = useL3SpiderUnmappedLineRules(open)
  const items = query.data?.items ?? []

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger asChild>
        <Button type="button" variant="outline" size="sm" className="h-8 gap-1.5 px-3 text-xs">
          <Wrench className="size-3.5" aria-hidden="true" />
          개발자 옵션
          {query.data ? (
            <Badge variant={items.length ? "destructive" : "secondary"} className="ml-0.5 h-4 px-1.5 text-[10px]">
              {items.length}
            </Badge>
          ) : null}
        </Button>
      </SheetTrigger>

      <SheetContent side="right" className="flex w-full max-w-[96vw] flex-col gap-0 p-0 sm:max-w-[920px]">
        <SheetHeader className="shrink-0 border-b py-4 pl-6 pr-16">
          <div className="flex min-w-0 items-center justify-between gap-4">
            <div className="min-w-0">
              <SheetTitle className="text-base">미매핑 Line 규칙</SheetTitle>
              <SheetDescription className="mt-1 flex flex-wrap items-center gap-2 text-xs">
                <code className="rounded bg-muted px-1.5 py-0.5 font-mono text-foreground">
                  {query.data?.rulesFile ?? "public.l3_spider_line_name_rule"}
                </code>
                <span>미매핑 {items.length.toLocaleString()}개</span>
              </SheetDescription>
            </div>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  type="button"
                  variant="outline"
                  size="icon"
                  className="size-8 shrink-0"
                  aria-label="미매핑 규칙 다시 조회"
                  onClick={() => query.refetch()}
                  disabled={query.isFetching}
                >
                  <RefreshCw className={`size-3.5 ${query.isFetching ? "animate-spin" : ""}`} aria-hidden="true" />
                </Button>
              </TooltipTrigger>
              <TooltipContent side="bottom">다시 조회</TooltipContent>
            </Tooltip>
          </div>
        </SheetHeader>

        <div className="min-h-0 min-w-0 flex-1 overflow-auto">
          {query.isLoading ? (
            <div className="flex h-48 items-center justify-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="size-4 animate-spin" aria-hidden="true" />
              미매핑 규칙을 조회하는 중입니다.
            </div>
          ) : query.isError ? (
            <div className="flex h-48 flex-col items-center justify-center gap-3 px-6 text-center">
              <AlertTriangle className="size-5 text-destructive" aria-hidden="true" />
              <p className="text-sm text-destructive">
                {query.error?.message || "미매핑 규칙을 조회하지 못했습니다."}
              </p>
              <Button type="button" variant="outline" size="sm" onClick={() => query.refetch()}>
                다시 조회
              </Button>
            </div>
          ) : items.length === 0 ? (
            <div className="flex h-48 flex-col items-center justify-center gap-2 text-sm text-muted-foreground">
              <CheckCircle2 className="size-5" aria-hidden="true" />
              미매핑된 분석 조합이 없습니다.
            </div>
          ) : (
            <Table>
              <TableHeader className="sticky top-0 z-10 bg-background">
                <TableRow>
                  <TableHead>Line ID</TableHead>
                  <TableHead>Process ID</TableHead>
                  <TableHead>Step Seq</TableHead>
                  <TableHead>최초 발견</TableHead>
                  <TableHead>최근 발견</TableHead>
                  <TableHead className="text-right">발견 일수</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.map((item) => (
                  <TableRow key={`${item.lineId}\u0000${item.processId}\u0000${item.stepSeq}`}>
                    <TableCell className="whitespace-nowrap font-mono text-xs font-semibold">
                      {item.lineId}
                    </TableCell>
                    <TableCell className="whitespace-nowrap font-mono text-xs">
                      {item.processId}
                    </TableCell>
                    <TableCell className="whitespace-nowrap font-mono text-xs">
                      {item.stepSeq}
                    </TableCell>
                    <TableCell className="whitespace-nowrap text-xs text-muted-foreground">
                      {item.firstSeenDate}
                    </TableCell>
                    <TableCell className="whitespace-nowrap text-xs text-muted-foreground">
                      {item.lastSeenDate}
                    </TableCell>
                    <TableCell className="text-right font-mono text-xs tabular-nums">
                      {Number(item.dateCount ?? 0).toLocaleString()}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </div>
      </SheetContent>
    </Sheet>
  )
}
