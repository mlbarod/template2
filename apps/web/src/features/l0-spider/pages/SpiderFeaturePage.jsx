import { useEffect, useMemo, useState } from "react"
import { ArrowLeft, Download, FileImage, LineChart, MailPlus, Save, Search, Trash2 } from "lucide-react"
import { Link } from "react-router-dom"
import { useQuery } from "@tanstack/react-query"
import {
  CartesianGrid,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  XAxis,
  YAxis,
} from "recharts"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { ChartTooltip } from "@/components/ui/chart"
import { cn } from "@/lib/utils"

import {
  FDC_LINES,
  SPIDER_FILE_PATHS,
  getRecipientRows,
  getSpiderAnomalyRows,
  getSpiderCommonalityRows,
  getSpiderHistoryRows,
  getSpiderSummaryRows,
  getTeamsByLine,
  getYieldSpecRows,
} from "../utils/l0SpiderMockData"
import { fetchHardSpecMeta, fetchHardSpecRecommendations } from "../api/l0SpiderApi"

const PAGE_META = {
  matching: {
    title: "동일성 이상감지",
    category: "Matching",
    description: "동일 조건의 설비별 FDC 분포 차이를 센서와 step 기준으로 조회합니다.",
  },
  common: {
    title: "공통부 이상감지",
    category: "Common",
    description: "공통부 이상 step과 ch_step 이미지를 센서 단위로 조회합니다.",
  },
  history: {
    title: "과거 이상감지 이력",
    category: "History",
    description: "이력저장된 이상감지 chart를 라인과 분임조 기준으로 확인합니다.",
  },
  manual: {
    title: "사용자 메뉴얼",
    category: "Manual",
    description: "Streamlit 앱에서 사용하던 사용자 매뉴얼 이미지 경로를 표시합니다.",
  },
  hardSpec: {
    title: "FDC Hard Limit추천",
    category: "Limit",
    description: "HDFS 통계와 기존 HARD_LIMIT 기준으로 추천 Spec 후보를 조회합니다.",
  },
  yieldSpec: {
    title: "수율기반 Hard Limit추천",
    category: "Yield",
    description: "P1F 수율 상/하위 그룹의 FDC 분포 차이로 Spec 후보를 조회합니다.",
  },
  recipients: {
    title: "이상감지 수신인 정비",
    category: "Recipients",
    description: "이상감지 메일 수신 대상과 sdwt, priority 조건을 등록하거나 제거합니다.",
  },
  defect: {
    title: "Defect SPIDER",
    category: "Defect",
    description: "Defect 신호 기반 이상 패턴을 공통부 조회 형식으로 탐색합니다.",
  },
  l1: {
    title: "L1 SPIDER",
    category: "Level 1",
    description: "L1 설비/공정 신호를 센서와 step 기준으로 조회합니다.",
  },
  l3: {
    title: "L3 SPIDER",
    category: "Level 3",
    description: "L3 연계 지표와 이상 흐름을 공통부 조회 형식으로 확인합니다.",
  },
}

const STEP_SEQ_OPTIONS = ["CR380250", "CR580250", "CR590180", "CR610200", "CU380250", "CU580250", "CU590180", "CU610200"]
const DEFAULT_LINE = FDC_LINES[0]
const SDWT_OPTIONS = FDC_LINES.flatMap((lineId) => getTeamsByLine(lineId))
const PRIORITY_OPTIONS = ["A", "B", "D", "M", "N"]
const HARD_SPEC_COLUMNS = ["priority", "sensor_name", "ch_step", "추천Spec(Lower)", "추천Spec(Upper)", "기존Spec(Lower)", "기존Spec(Upper)", "Spec격차"]
const HARD_SPEC_DEFAULT_LINE = "PFBP"

function getSdwtOptionsByLine(line) {
  return getTeamsByLine(line)
}

function PageShell({ children, description, title, category }) {
  return (
    <div className="flex h-full min-h-0 min-w-0 flex-col bg-background">
      <header className="shrink-0 border-b bg-card px-6 py-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="min-w-0">
            <div className="mb-2 flex items-center gap-2">
              <h1 className="truncate text-2xl font-semibold tracking-tight">{title}</h1>
              <Badge variant="outline">{category}</Badge>
            </div>
            <p className="text-sm text-muted-foreground">{description}</p>
          </div>
          <Button type="button" variant="outline" size="sm" asChild>
            <Link to="/l0_spider">
              <ArrowLeft className="size-4" aria-hidden="true" />
              SPIDER 메인
            </Link>
          </Button>
        </div>
      </header>

      <main className="min-h-0 flex-1 overflow-y-auto px-6 py-6">
        <div className="mx-auto grid w-full max-w-7xl gap-4">{children}</div>
      </main>
    </div>
  )
}

function SourcePathBar({ paths }) {
  return (
    <section className="rounded-lg border bg-card p-4">
      <div className="mb-3 flex items-center gap-2">
        <FileImage className="size-4 text-muted-foreground" aria-hidden="true" />
        <h2 className="text-sm font-semibold">SPIDER 데이터 기준 경로</h2>
      </div>
      <div className="grid gap-2">
        {paths.map((path) => (
          <code key={path} className="block truncate rounded-md bg-muted px-2 py-1.5 text-xs text-muted-foreground">
            {path}
          </code>
        ))}
      </div>
    </section>
  )
}

function SimpleTable({ columns, rows, selectedId, onSelectRow }) {
  return (
    <div className="overflow-hidden rounded-lg border bg-card">
      <Table>
        <TableHeader>
          <TableRow className="bg-muted/50">
            {columns.map((column) => (
              <TableHead key={column.key} className={column.className}>{column.label}</TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.length ? (
            rows.map((row) => (
              <TableRow
                key={row.id ?? row.file_path ?? row.email}
                className={cn(onSelectRow && "cursor-pointer hover:bg-muted/50", selectedId === row.id && "bg-primary/10")}
                onClick={() => onSelectRow?.(row)}
              >
                {columns.map((column) => (
                  <TableCell key={column.key} className={cn("align-middle", column.cellClassName)}>
                    {column.render ? column.render(row) : row[column.key]}
                  </TableCell>
                ))}
              </TableRow>
            ))
          ) : (
            <TableRow>
              <TableCell colSpan={columns.length} className="py-10 text-center text-sm text-muted-foreground">
                조회결과가 없습니다.
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>
    </div>
  )
}

function MetricGrid() {
  const { lineRows, sdwtRows } = getSpiderSummaryRows()
  const totalNg = lineRows.reduce((sum, row) => sum + row.NG, 0)
  const totalOk = lineRows.reduce((sum, row) => sum + row.OK, 0)
  const metrics = [
    ["모니터링 센서총합", totalOk + totalNg],
    ["감지 PPID 갯수", 42],
    ["전체 이상건수", totalNg],
    ["A/B Grade", lineRows.reduce((sum, row) => sum + row["A등급"] + row["B등급"], 0)],
    ["D Grade", lineRows.reduce((sum, row) => sum + row["D등급"], 0)],
    ["N Grade", lineRows.reduce((sum, row) => sum + row["N등급"], 0)],
    ["M Grade", lineRows.reduce((sum, row) => sum + row["M등급"], 0)],
  ]

  return (
    <section className="grid gap-4">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-7">
        {metrics.map(([label, value]) => (
          <div key={label} className="rounded-lg border bg-card px-4 py-3">
            <p className="truncate text-xs font-medium text-muted-foreground">{label}</p>
            <p className="mt-1 text-xl font-semibold tabular-nums">{value.toLocaleString()}</p>
          </div>
        ))}
      </div>
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <SummaryTable title="라인별 전체 Monitoring 건수" rows={lineRows} firstColumn="line_id" />
        <SummaryTable title="SDWT별 전체 Monitoring 건수" rows={sdwtRows} firstColumn="sdwt" />
      </div>
    </section>
  )
}

function SummaryTable({ title, rows, firstColumn }) {
  const columns = [
    { key: firstColumn, label: firstColumn },
    { key: "A등급", label: "A등급" },
    { key: "B등급", label: "B등급" },
    { key: "D등급", label: "D등급" },
    { key: "M등급", label: "M등급" },
    { key: "N등급", label: "N등급" },
    { key: "OK", label: "OK" },
    { key: "NG", label: "NG" },
    { key: "NG비율", label: "NG비율" },
  ]

  return (
    <section className="grid gap-3">
      <h2 className="text-sm font-semibold">{title}</h2>
      <SimpleTable
        columns={columns.map((column) => ({
          ...column,
          cellClassName: column.key === firstColumn ? "font-medium" : "text-right tabular-nums",
        }))}
        rows={rows.map((row) => ({ ...row, id: row[firstColumn] }))}
      />
    </section>
  )
}

function TrendPreviewChart({ row }) {
  const data = (row?.points ?? []).map((point, index) => ({ ...point, index: index + 1 }))

  return (
    <div className="h-[280px] rounded-lg border bg-card p-3">
      <ResponsiveContainer width="100%" height="100%">
        <ScatterChart margin={{ top: 12, right: 16, bottom: 12, left: 4 }}>
          <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" />
          <XAxis dataKey="wafer" type="category" tick={{ fontSize: 11, fill: "var(--muted-foreground)" }} />
          <YAxis dataKey="value" type="number" width={44} tick={{ fontSize: 11, fill: "var(--muted-foreground)" }} />
          <ReferenceLine y={row?.points?.[0]?.limit} stroke="var(--destructive)" strokeDasharray="4 4" />
          <ChartTooltip cursor={{ strokeDasharray: "3 3" }} />
          <Scatter data={data} dataKey="value" fill="var(--chart-1)" />
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  )
}

function MatchingPage({ common = false }) {
  const rows = common ? getSpiderCommonalityRows() : getSpiderAnomalyRows()
  const [line, setLine] = useState(DEFAULT_LINE)
  const sdwtOptions = getSdwtOptionsByLine(line)
  const [sdwt, setSdwt] = useState(sdwtOptions[0] ?? "")
  const [selectedId, setSelectedId] = useState(rows[0]?.id ?? "")
  const filteredRows = rows.filter((row) => row.line_id === line && row.sdwt === sdwt)
  const selectedRow = filteredRows.find((row) => row.id === selectedId) ?? filteredRows[0]
  const handleLineChange = (nextLine) => {
    const nextSdwtOptions = getSdwtOptionsByLine(nextLine)
    setLine(nextLine)
    setSdwt(nextSdwtOptions[0] ?? "")
    setSelectedId("")
  }
  const handleSdwtChange = (nextSdwt) => {
    setSdwt(nextSdwt)
    setSelectedId("")
  }
  const columns = common
    ? [
        { key: "priority", label: "priority" },
        { key: "step_seq", label: "step_seq" },
        { key: "step_desc", label: "step_desc", cellClassName: "font-medium" },
        { key: "sensor", label: "sensor" },
        { key: "ch_step", label: "ch_step" },
      ]
    : [
        { key: "grade", label: "센서 등급" },
        { key: "desc", label: "STEP", cellClassName: "font-medium" },
        { key: "sensor", label: "sensor" },
        { key: "eqp", label: "eqp" },
        { key: "abnormalCount", label: "이상 건수", cellClassName: "text-right tabular-nums" },
      ]

  return (
    <>
      <FilterBar
        line={line}
        sdwt={sdwt}
        sdwtOptions={sdwtOptions}
        onLineChange={handleLineChange}
        onSdwtChange={handleSdwtChange}
      />
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1fr)_420px]">
        <section className="grid gap-3">
          <div className="flex items-center justify-between gap-3">
            <h2 className="text-sm font-semibold">조회결과</h2>
            <Badge variant="secondary">총 {filteredRows.length}건</Badge>
          </div>
          <SimpleTable columns={columns} rows={filteredRows} selectedId={selectedRow?.id} onSelectRow={(row) => setSelectedId(row.id)} />
        </section>
        <section className="grid content-start gap-3">
          <div className="rounded-lg border bg-card p-4">
            <h2 className="text-sm font-semibold">{common ? "공통부 이미지 정보" : "동일성차트"}</h2>
            <p className="mt-1 truncate text-xs text-muted-foreground">{selectedRow?.file_path}</p>
          </div>
          <TrendPreviewChart row={selectedRow} />
          <div className="grid grid-cols-2 gap-2">
            <Button type="button" variant="outline" size="sm">
              <LineChart className="size-4" aria-hidden="true" />
              동일성차트
            </Button>
            <Button type="button" variant="outline" size="sm">
              <Search className="size-4" aria-hidden="true" />
              변경점 리스트
            </Button>
          </div>
        </section>
      </div>
      <SourcePathBar paths={common ? [SPIDER_FILE_PATHS.commonDate, SPIDER_FILE_PATHS.commonalityRoot] : [SPIDER_FILE_PATHS.erdRoot]} />
    </>
  )
}

function FilterBar({ line, sdwt, sdwtOptions = getSdwtOptionsByLine(line), onLineChange, onSdwtChange }) {
  return (
    <section className="grid gap-3 rounded-lg border bg-card p-4">
      <h2 className="text-sm font-semibold">조회조건 설정</h2>
      <div className="flex flex-wrap items-center gap-3">
        <div className="grid gap-1.5">
          <Label className="text-xs">라인 선택</Label>
          <Tabs value={line} onValueChange={onLineChange}>
            <TabsList>
              {FDC_LINES.map((lineId) => (
                <TabsTrigger key={lineId} value={lineId}>{lineId}</TabsTrigger>
              ))}
            </TabsList>
          </Tabs>
        </div>
        <div className="grid gap-1.5">
          <Label className="text-xs">분임조 선택</Label>
          <Tabs value={sdwt} onValueChange={onSdwtChange}>
            <TabsList>
              {sdwtOptions.map((option) => (
                <TabsTrigger key={option} value={option}>{option}</TabsTrigger>
              ))}
            </TabsList>
          </Tabs>
        </div>
      </div>
    </section>
  )
}

function HistoryPage() {
  const rows = getSpiderHistoryRows()
  const [selectedId, setSelectedId] = useState(rows[0]?.id ?? "")
  const selectedRow = rows.find((row) => row.id === selectedId) ?? rows[0]

  return (
    <>
      <FilterBar line={DEFAULT_LINE} sdwt={getSdwtOptionsByLine(DEFAULT_LINE)[0]} onLineChange={() => {}} onSdwtChange={() => {}} />
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1fr)_420px]">
        <SimpleTable
          columns={[
            { key: "update_date", label: "update_date" },
            { key: "sdwt", label: "sdwt" },
            { key: "sensor", label: "sensor", cellClassName: "font-medium" },
            { key: "eqp", label: "eqp" },
            {
              key: "action",
              label: "삭제",
              render: () => <Trash2 className="size-4 text-muted-foreground" aria-hidden="true" />,
            },
          ]}
          rows={rows}
          selectedId={selectedId}
          onSelectRow={(row) => setSelectedId(row.id)}
        />
        <section className="grid content-start gap-3">
          <div className="rounded-lg border bg-card p-4">
            <h2 className="text-sm font-semibold">저장 이력 Chart</h2>
            <p className="mt-1 truncate text-xs text-muted-foreground">{selectedRow?.file_path}</p>
          </div>
          <TrendPreviewChart row={getSpiderAnomalyRows()[0]} />
          <Button type="button" variant="outline" size="sm">
            <Save className="size-4" aria-hidden="true" />
            이력저장 경로 확인
          </Button>
        </section>
      </div>
      <SourcePathBar paths={[SPIDER_FILE_PATHS.backupRoot]} />
    </>
  )
}

function ManualPage() {
  return (
    <>
      <section className="grid min-h-[520px] place-items-center rounded-lg border bg-card p-8 text-center">
        <div className="grid max-w-xl justify-items-center gap-4">
          <div className="flex size-16 items-center justify-center rounded-lg border bg-muted">
            <FileImage className="size-8 text-muted-foreground" aria-hidden="true" />
          </div>
          <div>
            <h2 className="text-base font-semibold">사용자 메뉴얼 이미지</h2>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">
              개발 환경에서는 실제 `/appdata` 이미지를 브라우저에서 직접 읽지 않고, 원본 Streamlit 앱의 이미지 경로를 데이터 소스로 표시합니다.
            </p>
          </div>
          <code className="rounded-md bg-muted px-3 py-2 text-xs text-muted-foreground">{SPIDER_FILE_PATHS.manualImage}</code>
        </div>
      </section>
      <SourcePathBar paths={[SPIDER_FILE_PATHS.manualImage]} />
    </>
  )
}

function HardSpecPage() {
  const [line, setLine] = useState(HARD_SPEC_DEFAULT_LINE)
  const [stepSeq, setStepSeq] = useState("")
  const [recipeId, setRecipeId] = useState("")
  const [fdcModel, setFdcModel] = useState("")
  const [rows, setRows] = useState([])
  const [selectedRows, setSelectedRows] = useState(() => new Set())
  const metaQuery = useQuery({
    queryKey: ["fdc-hard-spec-meta", line, stepSeq, recipeId],
    queryFn: () => fetchHardSpecMeta({ lineId: line, stepSeq, recipeId }),
  })
  const recommendationQuery = useQuery({
    queryKey: ["fdc-hard-spec-recommendations", line, stepSeq, recipeId, fdcModel],
    queryFn: () => fetchHardSpecRecommendations({ lineId: line, stepSeq, recipeId, fdcModel }),
    enabled: false,
  })
  const meta = metaQuery.data
  const metaStepSeqs = meta?.stepSeqs
  const metaRecipeIds = meta?.recipeIds
  const metaFdcModels = meta?.fdcModels
  const stepOptions = useMemo(() => metaStepSeqs ?? [], [metaStepSeqs])
  const recipeOptions = useMemo(() => metaRecipeIds ?? [], [metaRecipeIds])
  const fdcModelOptions = useMemo(() => metaFdcModels ?? [], [metaFdcModels])
  const warningMessages = [
    ...(metaQuery.error ? [metaQuery.error.message] : []),
    ...(recommendationQuery.error ? [recommendationQuery.error.message] : []),
    ...(meta?.warnings ?? []),
    ...(recommendationQuery.data?.warnings ?? []),
  ].filter(Boolean)
  const chartRows = rows.filter((row) => selectedRows.has(row.id)).slice(0, 15)
  const guideRow = chartRows[0]
  const hardSpecSourcePaths = [
    meta?.sourcePaths?.hardSpecRoot ?? SPIDER_FILE_PATHS.hardSpecRoot,
    meta?.sourcePaths?.priority ?? SPIDER_FILE_PATHS.priority,
    meta?.sourcePaths?.unitModel ?? SPIDER_FILE_PATHS.unitModel,
    meta?.sourcePaths?.hardLimit ?? SPIDER_FILE_PATHS.hardLimit,
    ...(recommendationQuery.data?.sourcePaths ?? []).slice(0, 8),
  ]

  useEffect(() => {
    if (!meta) return
    if (meta.stepSeq && !stepSeq) setStepSeq(meta.stepSeq)
    if (meta.recipeId && !recipeId) setRecipeId(meta.recipeId)
    if (!fdcModel && fdcModelOptions.length) setFdcModel(fdcModelOptions[0])
  }, [fdcModel, fdcModelOptions, meta, recipeId, stepSeq])

  useEffect(() => {
    if (!recommendationQuery.data) return
    const nextRows = recommendationQuery.data.rows ?? []
    setRows(nextRows)
    setSelectedRows(new Set(nextRows.slice(0, 2).map((row) => row.id)))
  }, [recommendationQuery.data])

  const toggleRow = (row) => {
    setSelectedRows((current) => {
      const next = new Set(current)
      if (next.has(row.id)) next.delete(row.id)
      else next.add(row.id)
      return next
    })
  }
  const handleLineChange = (nextLine) => {
    setLine(nextLine)
    setStepSeq("")
    setRecipeId("")
    setFdcModel("")
    setRows([])
    setSelectedRows(new Set())
  }
  const handleStepChange = (nextStepSeq) => {
    setStepSeq(nextStepSeq)
    setRecipeId("")
    setFdcModel("")
    setRows([])
    setSelectedRows(new Set())
  }
  const handleRecipeChange = (nextRecipeId) => {
    setRecipeId(nextRecipeId)
    setFdcModel("")
    setRows([])
    setSelectedRows(new Set())
  }
  const searchRows = () => {
    if (!line || !stepSeq || !recipeId || !fdcModel) return
    recommendationQuery.refetch()
  }
  const downloadRows = () => {
    const csvRows = [
      HARD_SPEC_COLUMNS.join(","),
      ...rows.map((row) => HARD_SPEC_COLUMNS.map((column) => `"${String(row[column] ?? "").replaceAll('"', '""')}"`).join(",")),
    ]
    const blob = new Blob([csvRows.join("\n")], { type: "text/csv;charset=utf-8" })
    const url = URL.createObjectURL(blob)
    const link = document.createElement("a")
    link.href = url
    link.download = "hard-spec-recommendation.csv"
    link.click()
    URL.revokeObjectURL(url)
  }

  return (
    <>
      <section className="grid gap-4 rounded-lg border bg-card p-4">
        <div className="flex flex-wrap items-end gap-3">
          <Select value={line} onValueChange={handleLineChange}>
            <SelectTrigger className="w-[180px]"><SelectValue placeholder="라인ID 선택해주세요" /></SelectTrigger>
            <SelectContent>
              {(meta?.lineIds ?? [HARD_SPEC_DEFAULT_LINE]).map((lineId) => (
                <SelectItem key={lineId} value={lineId}>{lineId}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select value={stepSeq} onValueChange={handleStepChange}>
            <SelectTrigger className="w-[180px]"><SelectValue placeholder="step_seq 선택해주세요" /></SelectTrigger>
            <SelectContent>{stepOptions.map((option) => <SelectItem key={option} value={option}>{option}</SelectItem>)}</SelectContent>
          </Select>
          <Select value={recipeId} onValueChange={handleRecipeChange}>
            <SelectTrigger className="w-[180px]"><SelectValue placeholder="RecipeID 선택해주세요" /></SelectTrigger>
            <SelectContent>{recipeOptions.map((option) => <SelectItem key={option} value={option}>{option}</SelectItem>)}</SelectContent>
          </Select>
          <Select value={fdcModel} onValueChange={setFdcModel}>
            <SelectTrigger className="w-[180px]"><SelectValue placeholder="FDC Model 선택해주세요" /></SelectTrigger>
            <SelectContent>{fdcModelOptions.map((option) => <SelectItem key={option} value={option}>{option}</SelectItem>)}</SelectContent>
          </Select>
          <Button type="button" onClick={searchRows} disabled={!line || !stepSeq || !recipeId || !fdcModel || recommendationQuery.isFetching}>
            <Search className="size-4" aria-hidden="true" />
            추천SPEC 조회
          </Button>
          <Button type="button" variant="outline" onClick={downloadRows} disabled={!rows.length}>
            <Download className="size-4" aria-hidden="true" />
            엑셀 다운로드
          </Button>
        </div>
        {warningMessages.length ? (
          <div className="rounded-md border border-destructive/30 bg-destructive/5 px-3 py-2 text-xs text-destructive">
            {warningMessages[0]}
          </div>
        ) : null}
      </section>

      <SimpleTable
        columns={[
          {
            key: "select",
            label: "",
            render: (row) => <Checkbox checked={selectedRows.has(row.id)} onCheckedChange={() => toggleRow(row)} aria-label={`${row.sensor_name} 선택`} />,
          },
          { key: "priority", label: "priority" },
          { key: "sensor_name", label: "sensor_name", cellClassName: "font-medium" },
          { key: "ch_step", label: "ch_step" },
          { key: "추천Spec(Lower)", label: "추천Spec(Lower)", cellClassName: "text-right tabular-nums" },
          { key: "추천Spec(Upper)", label: "추천Spec(Upper)", cellClassName: "text-right tabular-nums" },
          { key: "기존Spec(Lower)", label: "기존Spec(Lower)", cellClassName: "text-right tabular-nums" },
          { key: "기존Spec(Upper)", label: "기존Spec(Upper)", cellClassName: "text-right tabular-nums" },
          { key: "Spec격차", label: "Spec격차", cellClassName: "text-right tabular-nums" },
        ]}
        rows={rows}
      />

      <section className="rounded-lg border bg-card p-4">
        <div className="mb-3 flex items-center justify-between gap-3">
          <h2 className="text-sm font-semibold">그래프 그리기</h2>
          <Badge variant="secondary">선택 {chartRows.length}개</Badge>
        </div>
        <div className="h-[340px]">
          <ResponsiveContainer width="100%" height="100%">
            <ScatterChart margin={{ top: 12, right: 18, bottom: 12, left: 4 }}>
              <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" />
              <XAxis dataKey="index" tick={{ fontSize: 11, fill: "var(--muted-foreground)" }} />
              <YAxis dataKey="value" width={48} tick={{ fontSize: 11, fill: "var(--muted-foreground)" }} />
              <ChartTooltip />
              {guideRow ? <ReferenceLine y={guideRow["추천Spec(Lower)"]} stroke="var(--destructive)" strokeDasharray="4 4" /> : null}
              {guideRow ? <ReferenceLine y={guideRow["추천Spec(Upper)"]} stroke="var(--destructive)" strokeDasharray="4 4" /> : null}
              {guideRow ? <ReferenceLine y={guideRow["기존Spec(Lower)"]} stroke="var(--chart-2)" strokeDasharray="4 4" /> : null}
              {guideRow ? <ReferenceLine y={guideRow["기존Spec(Upper)"]} stroke="var(--chart-2)" strokeDasharray="4 4" /> : null}
              {chartRows.map((row, index) => (
                <Scatter key={row.id} name={row.sensor_name} data={(row.points ?? []).map((point, pointIndex) => ({ index: pointIndex + 1, value: point.param_value }))} dataKey="value" fill={`var(--chart-${(index % 5) + 1})`} />
              ))}
            </ScatterChart>
          </ResponsiveContainer>
        </div>
      </section>
      <SourcePathBar paths={hardSpecSourcePaths} />
    </>
  )
}

function YieldSpecPage() {
  const [stepSeq, setStepSeq] = useState(STEP_SEQ_OPTIONS[0])
  const rows = getYieldSpecRows(stepSeq)

  return (
    <>
      <section className="grid gap-4 rounded-lg border bg-card p-4">
        <div className="flex flex-wrap items-end gap-3">
          <Select value={stepSeq} onValueChange={setStepSeq}>
            <SelectTrigger className="w-[220px]"><SelectValue placeholder="Step seq 를 선택해주세요." /></SelectTrigger>
            <SelectContent>{STEP_SEQ_OPTIONS.map((option) => <SelectItem key={option} value={option}>{option}</SelectItem>)}</SelectContent>
          </Select>
          <Select defaultValue={rows[0]?.recipe_id}>
            <SelectTrigger className="w-[180px]"><SelectValue placeholder="Recipe id" /></SelectTrigger>
            <SelectContent>{rows.slice(0, 4).map((row) => <SelectItem key={row.recipe_id} value={row.recipe_id}>{row.recipe_id}</SelectItem>)}</SelectContent>
          </Select>
          <Button type="button">
            <Search className="size-4" aria-hidden="true" />
            조회
          </Button>
        </div>
        <p className="text-xs text-muted-foreground">g_min, g_max : 수율 상위 50% 물량의 MIN MAX / b_min, b_max : 수율 하위 50% 물량의 MIN MAX</p>
      </section>
      <SimpleTable
        columns={[
          { key: "step_seq", label: "step_seq" },
          { key: "recipe_id", label: "recipe_id" },
          { key: "fdc_parameter", label: "fdc_parameter", cellClassName: "font-medium" },
          { key: "g_min", label: "g_min", cellClassName: "text-right tabular-nums" },
          { key: "g_max", label: "g_max", cellClassName: "text-right tabular-nums" },
          { key: "b_min", label: "b_min", cellClassName: "text-right tabular-nums" },
          { key: "b_max", label: "b_max", cellClassName: "text-right tabular-nums" },
        ]}
        rows={rows}
      />
      <SourcePathBar paths={[SPIDER_FILE_PATHS.yieldRoot, SPIDER_FILE_PATHS.yieldImage]} />
    </>
  )
}

function RecipientsPage() {
  const [rows, setRows] = useState(getRecipientRows)
  const [email, setEmail] = useState("t1232.kang")
  const [selectedSdwt, setSelectedSdwt] = useState(() => new Set(["Lambda_H1L"]))
  const [selectedPriority, setSelectedPriority] = useState(() => new Set(PRIORITY_OPTIONS))

  const toggleSet = (setter, value) => {
    setter((current) => {
      const next = new Set(current)
      if (next.has(value)) next.delete(value)
      else next.add(value)
      return next
    })
  }
  const register = () => {
    if (!email || selectedSdwt.size === 0) return
    const nextRow = {
      email: email.split("@")[0],
      sdwt: JSON.stringify(Array.from(selectedSdwt).sort()),
      priority: JSON.stringify(Array.from(selectedPriority).sort()),
    }
    setRows((current) => [nextRow, ...current.filter((row) => row.email !== nextRow.email)])
  }
  const remove = () => {
    setRows((current) => current.filter((row) => row.email !== email.split("@")[0]))
  }

  return (
    <>
      <section className="grid gap-4 rounded-lg border bg-card p-4">
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,260px)_minmax(0,1fr)_minmax(0,1fr)_auto]">
          <div className="grid gap-1.5">
            <Label htmlFor="recipient-email">이메일</Label>
            <Input id="recipient-email" value={email} onChange={(event) => setEmail(event.target.value)} placeholder="t1232.kang" />
          </div>
          <OptionChecklist title="sdwt" options={SDWT_OPTIONS} selected={selectedSdwt} onToggle={(value) => toggleSet(setSelectedSdwt, value)} />
          <OptionChecklist title="priority" options={PRIORITY_OPTIONS} selected={selectedPriority} onToggle={(value) => toggleSet(setSelectedPriority, value)} />
          <div className="flex items-end gap-2">
            <Button type="button" onClick={register}>
              <MailPlus className="size-4" aria-hidden="true" />
              등록
            </Button>
            <Button type="button" variant="outline" onClick={remove}>제거</Button>
          </div>
        </div>
      </section>
      <SimpleTable
        columns={[
          { key: "email", label: "email", cellClassName: "font-medium" },
          { key: "sdwt", label: "sdwt" },
          { key: "priority", label: "priority" },
        ]}
        rows={rows}
      />
    </>
  )
}

function OptionChecklist({ title, options, selected, onToggle }) {
  return (
    <div className="grid gap-2">
      <Label>{title}</Label>
      <div className="flex flex-wrap gap-2">
        {options.map((option) => (
          <label key={option} className="flex h-9 items-center gap-2 rounded-md border bg-background px-3 text-xs">
            <Checkbox checked={selected.has(option)} onCheckedChange={() => onToggle(option)} />
            <span>{option}</span>
          </label>
        ))}
      </div>
    </div>
  )
}

export function SpiderFeaturePage({ type }) {
  const meta = PAGE_META[type] ?? PAGE_META.manual

  return (
    <PageShell title={meta.title} category={meta.category} description={meta.description}>
      {type === "matching" ? <MatchingPage /> : null}
      {type === "common" ? <MatchingPage common /> : null}
      {type === "history" ? <HistoryPage /> : null}
      {type === "manual" ? <ManualPage /> : null}
      {type === "hardSpec" ? <HardSpecPage /> : null}
      {type === "yieldSpec" ? <YieldSpecPage /> : null}
      {type === "recipients" ? <RecipientsPage /> : null}
      {type === "defect" ? <MatchingPage common /> : null}
      {type === "l1" ? <MatchingPage /> : null}
      {type === "l3" ? <MatchingPage common /> : null}
      {type === "summary" ? <MetricGrid /> : null}
      <SourcePathBar paths={[SPIDER_FILE_PATHS.dbInfo, SPIDER_FILE_PATHS.latestPath, SPIDER_FILE_PATHS.latestStats]} />
    </PageShell>
  )
}
