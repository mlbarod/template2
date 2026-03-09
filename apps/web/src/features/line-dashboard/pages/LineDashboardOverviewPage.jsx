// 파일 경로: src/features/line-dashboard/pages/LineDashboardOverviewPage.jsx
// 공정 요약을 붙일 개요 페이지입니다.
import {
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from "react"

import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/common"
import { DataTablePagination } from "../components/DataTablePagination"
import { getAirflowDagOverview } from "../api/getAirflowDagOverview"
import { numberFormatter } from "../utils/dataTableConstants"

function formatDate(dateLike) {
  if (!dateLike) return "—"
  const date = new Date(dateLike)
  if (Number.isNaN(date.getTime())) return "—"
  return new Intl.DateTimeFormat("ko-KR", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date)
}

function getStatusBadge(dag) {
  if (dag.isPaused) {
    return (
      <span className="inline-flex items-center rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-700 dark:bg-amber-400/20 dark:text-amber-200">
        Paused
      </span>
    )
  }

  return (
    <span className="inline-flex items-center rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-medium text-emerald-700 dark:bg-emerald-400/20 dark:text-emerald-200">
      Active
    </span>
  )
}

function getRunBadge(run) {
  if (!run?.state) {
    return (
      <span className="inline-flex items-center rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600 dark:bg-slate-700/40 dark:text-slate-200">
        No runs
      </span>
    )
  }

  const normalized = run.state.toLowerCase()

  if (normalized === "success") {
    return (
      <span className="inline-flex items-center rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-medium text-emerald-700 dark:bg-emerald-400/20 dark:text-emerald-200">
        Success
      </span>
    )
  }

  if (normalized === "failed") {
    return (
      <span className="inline-flex items-center rounded-full bg-rose-100 px-2 py-0.5 text-xs font-medium text-rose-700 dark:bg-rose-400/20 dark:text-rose-200">
        Failed
      </span>
    )
  }

  return (
    <span className="inline-flex items-center rounded-full bg-sky-100 px-2 py-0.5 text-xs font-medium text-sky-700 dark:bg-sky-400/20 dark:text-sky-200">
      {run.state}
    </span>
  )
}

function renderTagList(tags) {
  if (!tags?.length) return <span className="text-xs text-muted-foreground">—</span>
  return (
    <div className="flex flex-wrap gap-1">
      {tags.map((tag) => (
        <span
          key={tag}
          className="inline-flex items-center rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground"
        >
          {tag}
        </span>
      ))}
    </div>
  )
}

function renderOwnerList(owners) {
  if (!owners?.length) return <span className="text-xs text-muted-foreground">—</span>
  return (
    <div className="flex flex-wrap gap-1">
      {owners.map((owner) => (
        <span
          key={owner}
          className="inline-flex items-center rounded-md bg-slate-100 px-2 py-0.5 text-xs text-slate-700 dark:bg-slate-700/40 dark:text-slate-200"
        >
          {owner}
        </span>
      ))}
    </div>
  )
}

const initialState = { status: "idle", overview: null, error: null }

// ✅ 데이터가 있을 때만 “아래 빈 공간을 가로 라인(border)”로 채우기
const ROW_HEIGHT = 56 // h-14
const HEADER_HEIGHT = 48 // h-12
const MIN_VISIBLE_ROWS = 6
const PAGINATION_LABELS = {
  showing: "Showing",
  rows: "rows",
  filteredFrom: " (filtered from ",
  filteredFromSuffix: ")",
  rowsPerPage: "Rows per page",
  page: "Page",
  of: "of",
  goFirst: "Go to first page",
  goPrev: "Go to previous page",
  goNext: "Go to next page",
  goLast: "Go to last page",
}

export function LineDashboardOverviewPage() {
  const [{ status, overview, error }, setState] = useState(initialState)
  const [pagination, setPagination] = useState({ pageIndex: 0, pageSize: 15 })

  const tableViewportRef = useRef(null)
  const [fillerCount, setFillerCount] = useState(0)

  useEffect(() => {
    let active = true

    async function loadOverview() {
      setState({ status: "loading", overview: null, error: null })
      try {
        const result = await getAirflowDagOverview()
        if (!active) return
        if (result?.error) {
          setState({ status: "error", overview: result, error: result.error })
        } else {
          setState({ status: "success", overview: result, error: null })
        }
      } catch (err) {
        if (!active) return
        setState({
          status: "error",
          overview: null,
          error: err?.message ?? "Airflow DAG 정보를 불러오지 못했습니다.",
        })
      }
    }

    loadOverview()
    return () => {
      active = false
    }
  }, [])

  const dags = useMemo(() => overview?.dags ?? [], [overview])
  const totals = overview?.totals ?? { total: 0, active: 0, paused: 0, failed: 0 }
  const totalLoaded = dags.length
  const totalPages = Math.max(Math.ceil(totalLoaded / pagination.pageSize), 1)
  const safePageIndex = Math.min(pagination.pageIndex, totalPages - 1)
  const startIndex = safePageIndex * pagination.pageSize
  const endIndex = startIndex + pagination.pageSize
  const pagedDags = dags.slice(startIndex, endIndex)
  const currentPage = safePageIndex + 1
  const currentPageSize = pagedDags.length
  const hasRows = pagedDags.length > 0

  useEffect(() => {
    const maxIndex = Math.max(totalPages - 1, 0)
    setPagination((previous) =>
      previous.pageIndex > maxIndex ? { ...previous, pageIndex: maxIndex } : previous
    )
  }, [totalPages])

  useLayoutEffect(() => {
    function computeFiller() {
      const el = tableViewportRef.current
      if (!el) return

      if (!hasRows) {
        setFillerCount(0)
        return
      }

      const viewportHeight = el.clientHeight
      const available = Math.max(0, viewportHeight - HEADER_HEIGHT)

      const rowsFit = Math.max(0, Math.floor(available / ROW_HEIGHT))
      const targetRows = Math.max(MIN_VISIBLE_ROWS, rowsFit)
      const nextFiller = Math.max(0, targetRows - pagedDags.length)

      setFillerCount(nextFiller)
    }

    computeFiller()

    const el = tableViewportRef.current
    if (!el || typeof ResizeObserver === "undefined") {
      window.addEventListener("resize", computeFiller)
      return () => window.removeEventListener("resize", computeFiller)
    }

    const ro = new ResizeObserver(() => computeFiller())
    ro.observe(el)
    return () => ro.disconnect()
  }, [pagedDags.length, hasRows])

  if (status === "loading") {
    return (
      <section className="flex h-full min-h-0 min-w-0 flex-col gap-4 overflow-y-auto">
        <Card>
          <CardHeader>
            <CardTitle>Airflow DAG Overview</CardTitle>
            <CardDescription>Loading Airflow metadata...</CardDescription>
          </CardHeader>
          <div className="px-6 pb-6">
            <p className="text-sm text-muted-foreground">잠시만 기다려 주세요.</p>
          </div>
        </Card>
      </section>
    )
  }

  if (status === "error" || overview?.error || error) {
    return (
      <section className="flex h-full min-h-0 min-w-0 flex-col gap-4 overflow-y-auto">
        <Card>
          <CardHeader>
            <CardTitle>Airflow DAG Overview</CardTitle>
            <CardDescription>
              Airflow API 에 접근하는 동안 오류가 발생했습니다. 설정을 확인해 주세요.
            </CardDescription>
          </CardHeader>
          <div className="space-y-3 px-6 pb-6">
            <p className="text-sm text-destructive">{error || overview?.error}</p>
            <p className="text-sm text-muted-foreground">
              Airflow 이 <code className="rounded bg-muted px-1 py-0.5">{overview?.baseUrl}</code>
              에서 실행 중인지, 필요한 경우 <code>AIRFLOW_USERNAME</code> 과{" "}
              <code>AIRFLOW_PASSWORD</code>
              환경 변수가 설정되어 있는지 확인하세요.
            </p>
          </div>
        </Card>
      </section>
    )
  }

  return (
    <section className="grid h-full min-h-0 min-w-0 grid-rows-[auto,1fr] gap-4 overflow-hidden">
      {/* KPI 카드들 */}
      <div className="grid gap-4 md:grid-cols-3 xl:grid-cols-4">
        <Card>
          <CardHeader>
            <CardDescription>Total DAGs</CardDescription>
            <CardTitle className="text-3xl font-semibold">{totals.total}</CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader>
            <CardDescription>Active</CardDescription>
            <CardTitle className="text-3xl font-semibold text-emerald-600 dark:text-emerald-300">
              {totals.active}
            </CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader>
            <CardDescription>Paused</CardDescription>
            <CardTitle className="text-3xl font-semibold text-amber-600 dark:text-amber-300">
              {totals.paused}
            </CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader>
            <CardDescription>Last Run Failed</CardDescription>
            <CardTitle className="text-3xl font-semibold text-rose-600 dark:text-rose-300">
              {totals.failed}
            </CardTitle>
          </CardHeader>
        </Card>
      </div>

      {/* ✅ 하단: Card 대신 div로, Card와 "동일한 디자인" (border/radius/bg/shadow/padding) */}
      <div className="flex min-h-0 min-w-0 flex-col overflow-hidden rounded-xl border bg-card text-card-foreground shadow">
        {/* header: CardHeader와 동일한 패딩/구조 */}
        <div className="flex flex-col gap-2 p-6 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <div className="text-2xl font-semibold leading-none tracking-tight">
              Airflow DAG Overview
            </div>
            <p className="text-sm text-muted-foreground">
              Airflow 에서 제공한 DAG 목록과 최근 실행 결과를 확인할 수 있습니다.
            </p>
          </div>
          <p className="text-xs text-muted-foreground">
            Last updated: {formatDate(overview?.fetchedAt)}
          </p>
        </div>

        <div className="flex min-h-0 min-w-0 flex-1 flex-col px-6 pb-6">
          {/* content: CardContent와 동일한 패딩 + 스크롤 영역 */}
          <div className="min-h-0 min-w-0 flex-1 overflow-auto">
            {/* 이 div 높이를 기준으로 filler 계산 */}
            <div ref={tableViewportRef} className="h-full min-h-0 min-w-0">
              <Table stickyHeader>
                <TableHeader>
                  <TableRow className="h-12">
                    <TableHead className="h-12">DAG</TableHead>
                    <TableHead className="h-12">Status</TableHead>
                    <TableHead className="h-12">Latest Run</TableHead>
                    <TableHead className="h-12">Schedule</TableHead>
                    <TableHead className="h-12">Owners</TableHead>
                    <TableHead className="h-12">Tags</TableHead>
                    <TableHead className="h-12">Next Run</TableHead>
                  </TableRow>
                </TableHeader>

                <TableBody>
                  {totalLoaded === 0 ? (
                    <TableRow>
                      <TableCell colSpan={7} className="py-10 text-center text-sm text-muted-foreground">
                        등록된 DAG 가 없습니다.
                      </TableCell>
                    </TableRow>
                  ) : (
                    <>
                      {pagedDags.map((dag, index) => {
                        const airflowDagUrl = `${overview?.baseUrl}/dags/${encodeURIComponent(
                          dag.dagId
                        )}/grid`
                        const latestExecution = dag.latestRun?.executionDate
                        return (
                          <TableRow key={dag.dagId || `dag-${index}`} className="h-14">
                            <TableCell className="align-middle">
                              <div className="flex flex-col gap-1">
                                <a
                                  href={airflowDagUrl}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="font-medium text-primary hover:underline"
                                >
                                  {dag.dagId || "(unnamed)"}
                                </a>
                                {dag.description && (
                                  <span className="text-xs text-muted-foreground">{dag.description}</span>
                                )}
                              </div>
                            </TableCell>
                            <TableCell className="align-middle">{getStatusBadge(dag)}</TableCell>
                            <TableCell className="align-middle">
                              <div className="flex flex-col gap-1">
                                {getRunBadge(dag.latestRun)}
                                {latestExecution && (
                                  <span className="text-xs text-muted-foreground">
                                    {formatDate(latestExecution)}
                                  </span>
                                )}
                              </div>
                            </TableCell>
                            <TableCell className="align-middle">
                              <span className="text-xs text-muted-foreground">{dag.timetable || "—"}</span>
                            </TableCell>
                            <TableCell className="align-middle">{renderOwnerList(dag.owners)}</TableCell>
                            <TableCell className="align-middle">{renderTagList(dag.tags)}</TableCell>
                            <TableCell className="align-middle">
                              <span className="text-xs text-muted-foreground">{formatDate(dag.nextRun)}</span>
                            </TableCell>
                          </TableRow>
                        )
                      })}

                      {/* ✅ 데이터가 있을 때만 filler border 라인 */}
                      {Array.from({ length: fillerCount }).map((_, i) => (
                        <TableRow key={`filler-${i}`} className="h-14 pointer-events-none">
                          <TableCell colSpan={7} className=" bg-background p-0" />
                        </TableRow>
                      ))}
                    </>
                  )}
                </TableBody>
              </Table>
            </div>
          </div>

          <DataTablePagination
            labels={PAGINATION_LABELS}
            numberFormatter={numberFormatter}
            table={{
              getCanPreviousPage: () => safePageIndex > 0,
              getCanNextPage: () => safePageIndex < totalPages - 1,
              previousPage: () =>
                setPagination((previous) => ({
                  ...previous,
                  pageIndex: Math.max(previous.pageIndex - 1, 0),
                })),
              nextPage: () =>
                setPagination((previous) => ({
                  ...previous,
                  pageIndex: Math.min(previous.pageIndex + 1, totalPages - 1),
                })),
              setPageIndex: (pageIndex) =>
                setPagination((previous) => ({
                  ...previous,
                  pageIndex: Math.min(Math.max(pageIndex, 0), totalPages - 1),
                })),
              setPageSize: (pageSize) =>
                setPagination({
                  pageIndex: 0,
                  pageSize,
                }),
            }}
            currentPage={currentPage}
            totalPages={totalPages}
            currentPageSize={currentPageSize}
            filteredTotal={totalLoaded}
            totalLoaded={totalLoaded}
            pagination={pagination}
          />
        </div>
      </div>
    </section>
  )
}
