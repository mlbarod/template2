import { useEffect, useMemo, useRef, useState } from "react"
import {
  ArrowLeft,
  ArrowUp,
  BarChart3,
  ChevronRight,
} from "lucide-react"
import { Link } from "react-router-dom"
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
import { Card, CardContent, CardTitle } from "@/components/ui/card"
import { ChartTooltip, ChartTooltipContent } from "@/components/ui/chart"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { cn } from "@/lib/utils"

import {
  FDC_LINES,
  SENSOR_GRADES,
  getTeamsByLine,
  getTrendSteps,
} from "../utils/l0SpiderMockData"

const TREND_TYPE_LABELS = {
  "upper-shift": "상한 이동",
  variance: "분산 확대",
  cluster: "군집 이상",
  drift: "점진 Drift",
}
const CHARTS_PER_EQUIPMENT = 4

function formatTrendType(value) {
  return TREND_TYPE_LABELS[value] ?? value
}

function buildSensorChartVariants({ sensor, selectedStep, equipmentId, equipmentName }) {
  return Array.from({ length: CHARTS_PER_EQUIPMENT }, (_, index) => {
    const stepOffset = index + 1
    const stepCodeNumber = Number.parseInt(selectedStep.stepCode.replace(/\D/g, ""), 10) || 1200
    const chartStepCode = `STEP-${String(stepCodeNumber + stepOffset * 7).padStart(4, "0")}`
    const chartStepName = `${selectedStep.stepName} CH-${stepOffset}`
    const valueOffset = stepOffset * 0.65

    return {
      ...sensor,
      id: `${sensor.id}-chart-${stepOffset}`,
      equipmentId,
      equipmentName,
      chartStepCode,
      chartStepName,
      points: sensor.points.map((point) => ({
        ...point,
        value: Number((point.value + valueOffset).toFixed(2)),
      })),
    }
  })
}

function buildComparisonPoints(sensor) {
  return sensor.points.map((point, index) => ({
    ...point,
    value: Number((point.value + Math.sin((index + 1) / 2) * 1.8 - 1.2).toFixed(2)),
    status: index % 6 === 0 ? "abnormal" : point.status,
  }))
}

function buildChangePointItems(sensor) {
  const abnormalPoints = sensor.points.filter((point) => point.status === "abnormal").slice(0, 5)

  return abnormalPoints.map((point, index) => ({
    id: `${sensor.id}-change-${index}`,
    title: `${sensor.chartStepCode} ${point.wafer}`,
    description: `${point.time} 기준 ${sensor.sensorName} 값이 ${point.value}로 limit ${point.limit}을 초과했습니다.`,
  }))
}

function TrendStepButton({ step, selected, onSelect }) {
  return (
    <button
      type="button"
      onClick={onSelect}
      className={cn(
        "flex h-9 w-full min-w-0 items-center justify-between gap-3 rounded-md border border-transparent px-3 text-left transition hover:border-border hover:bg-muted/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        selected && "border-primary/30 bg-primary/10 text-primary shadow-sm",
      )}
    >
      <span
        className={cn(
          "min-w-0 flex-1 truncate text-[13px] font-medium leading-5 text-foreground",
          selected && "text-primary",
        )}
      >
        {step.stepName}
      </span>
      <span className="shrink-0 rounded-md bg-muted px-1.5 py-0.5 text-[11px] font-medium text-muted-foreground">
        {step.equipmentCount}대
      </span>
      <span className="min-w-12 shrink-0 text-right text-xs font-semibold tabular-nums">
        {step.abnormalCount}건수
      </span>
      <span className="shrink-0 text-muted-foreground">
        <ChevronRight className="size-3" aria-hidden="true" />
      </span>
    </button>
  )
}

function SensorButton({ sensor, selected, onSelect }) {
  return (
    <button
      type="button"
      onClick={onSelect}
      className={cn(
        "flex min-w-0 items-center justify-between gap-3 rounded-md border border-transparent px-3 py-2.5 text-left transition hover:border-border hover:bg-muted/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        selected && "border-primary/30 bg-primary/10 text-primary shadow-sm",
      )}
    >
      <span className="min-w-0">
        <span
          className={cn(
            "block truncate text-[13px] font-medium leading-5 text-foreground",
            selected && "text-primary",
          )}
        >
          {sensor.sensorName}
        </span>
        <span className="mt-1 block truncate text-[11px] font-medium leading-4 text-muted-foreground">
          Grade {sensor.grade} · {formatTrendType(sensor.trendType)} · {sensor.equipmentCount}대
        </span>
      </span>
      <span className="min-w-14 shrink-0 rounded-md bg-muted px-1.5 py-0.5 text-right text-xs font-semibold tabular-nums">
        {sensor.abnormalCount}건수
      </span>
    </button>
  )
}

function SensorGradeButton({ grade, selected, onToggle }) {
  return (
    <button
      type="button"
      aria-pressed={selected}
      onClick={onToggle}
      className={cn(
        "h-8 rounded-md border px-3 text-xs font-semibold transition hover:bg-muted/70 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        selected
          ? "border-primary bg-primary text-primary-foreground"
          : "border-input bg-background text-muted-foreground",
      )}
    >
      {grade}
    </button>
  )
}

function ScatterTooltip({ active, payload }) {
  if (!active || !payload?.length) return null
  const row = payload[0]?.payload
  if (!row) return null

  return (
    <ChartTooltipContent
      active={active}
      payload={[
        { dataKey: "wafer", name: "Wafer", value: row.wafer },
        { dataKey: "lot", name: "Lot", value: row.lot },
        { dataKey: "time", name: "Time", value: row.time },
        { dataKey: "value", name: "Value", value: row.value },
      ]}
      hideLabel
    />
  )
}

function FdcScatterChart({ selectedStep, sensor, selected }) {
  const [comparisonOpen, setComparisonOpen] = useState(false)
  const [changeListOpen, setChangeListOpen] = useState(false)
  const comparisonPoints = useMemo(
    () => (comparisonOpen ? buildComparisonPoints(sensor) : []),
    [comparisonOpen, sensor],
  )
  const changePointItems = useMemo(
    () => (changeListOpen ? buildChangePointItems(sensor) : []),
    [changeListOpen, sensor],
  )

  if (!selectedStep || !sensor) {
    return (
      <div className="flex h-72 items-center justify-center rounded-lg border bg-card text-sm text-muted-foreground">
        STEP과 FDC 센서를 선택하면 scatter chart가 표시됩니다.
      </div>
    )
  }

  return (
    <>
      <div
        className={cn(
          "grid h-[320px] min-h-0 grid-rows-[40px_minmax(0,1fr)_44px] gap-0 rounded-lg border bg-card",
          selected && "border-primary",
        )}
      >
        <div className="min-w-0 border-b bg-muted/60 px-2 py-1">
          <h3 className="truncate text-[13px] font-semibold leading-4">{sensor.sensorName}</h3>
          <p className="truncate text-[11px] leading-4 text-muted-foreground">
            Grade {sensor.grade} · {sensor.equipmentName} · PPID_CHSTEP: {sensor.chartStepCode ?? selectedStep.stepCode}_{sensor.chartStepName ?? selectedStep.stepName}
          </p>
        </div>
        <div className="h-full min-h-0 bg-background p-0">
          <ResponsiveContainer width="100%" height="100%">
            <ScatterChart margin={{ top: 8, right: 12, bottom: 12, left: 2 }}>
              <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" />
              <XAxis
                type="category"
                dataKey="wafer"
                tick={{ fontSize: 11, fill: "var(--muted-foreground)" }}
                tickLine={false}
                axisLine={{ stroke: "var(--border)" }}
                interval={2}
              />
              <YAxis
                type="number"
                dataKey="value"
                domain={["dataMin - 4", "dataMax + 4"]}
                tick={{ fontSize: 11, fill: "var(--muted-foreground)" }}
                tickLine={false}
                axisLine={{ stroke: "var(--border)" }}
                width={44}
              />
              <ReferenceLine
                y={sensor.points[0]?.limit}
                stroke="var(--destructive)"
                strokeDasharray="4 4"
                label={{ value: "Limit", fill: "var(--destructive)", fontSize: 11 }}
              />
              <ChartTooltip cursor={{ strokeDasharray: "3 3" }} content={<ScatterTooltip />} />
              <Scatter
                name="FDC Value"
                data={sensor.points}
                dataKey="value"
                fill="var(--chart-1)"
                shape={(props) => {
                  const { cx, cy, payload } = props
                  const abnormal = payload?.status === "abnormal"
                  return (
                    <circle
                      cx={cx}
                      cy={cy}
                      r={abnormal ? 5 : 4}
                      fill={abnormal ? "var(--destructive)" : "var(--chart-1)"}
                      stroke={abnormal ? "var(--destructive)" : "var(--background)"}
                      strokeWidth={1.5}
                    />
                  )
                }}
              />
            </ScatterChart>
          </ResponsiveContainer>
        </div>
        <div className="grid grid-cols-4 gap-1 border-t bg-card p-1.5">
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="h-8 min-w-0 px-1 text-xs"
            onClick={() => setComparisonOpen(true)}
          >
            동일성차트
          </Button>
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="h-8 min-w-0 px-1 text-xs"
            onClick={() => setChangeListOpen(true)}
          >
            변경점 리스트
          </Button>
          <Button type="button" variant="outline" size="sm" className="h-8 min-w-0 px-1 text-xs">
            이력저장
          </Button>
          <Button type="button" variant="secondary" size="sm" className="h-8 min-w-0 px-1 text-xs">
            SKIP
          </Button>
        </div>
      </div>
      <Dialog open={comparisonOpen} onOpenChange={setComparisonOpen}>
        <DialogContent className="grid max-h-[85vh] max-w-3xl grid-rows-[auto_minmax(0,1fr)] overflow-hidden">
          <DialogHeader>
            <DialogTitle>동일성차트</DialogTitle>
            <DialogDescription>
              {sensor.equipmentName} · {sensor.sensorName} · PPID_CHSTEP {sensor.chartStepCode}
            </DialogDescription>
          </DialogHeader>
          <div className="h-[420px] min-h-0 rounded-lg border bg-background p-2">
            {comparisonOpen ? (
              <ResponsiveContainer width="100%" height="100%">
                <ScatterChart margin={{ top: 12, right: 16, bottom: 16, left: 4 }}>
                  <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" />
                  <XAxis
                    type="category"
                    dataKey="wafer"
                    tick={{ fontSize: 11, fill: "var(--muted-foreground)" }}
                    tickLine={false}
                    axisLine={{ stroke: "var(--border)" }}
                    interval={2}
                  />
                  <YAxis
                    type="number"
                    dataKey="value"
                    domain={["dataMin - 4", "dataMax + 4"]}
                    tick={{ fontSize: 11, fill: "var(--muted-foreground)" }}
                    tickLine={false}
                    axisLine={{ stroke: "var(--border)" }}
                    width={48}
                  />
                  <ReferenceLine
                    y={sensor.points[0]?.limit}
                    stroke="var(--destructive)"
                    strokeDasharray="4 4"
                    label={{ value: "Limit", fill: "var(--destructive)", fontSize: 11 }}
                  />
                  <ChartTooltip cursor={{ strokeDasharray: "3 3" }} content={<ScatterTooltip />} />
                  <Scatter name="동일성 FDC Value" data={comparisonPoints} dataKey="value" fill="var(--chart-2)" />
                </ScatterChart>
              </ResponsiveContainer>
            ) : null}
          </div>
        </DialogContent>
      </Dialog>
      <Dialog open={changeListOpen} onOpenChange={setChangeListOpen}>
        <DialogContent className="max-w-xl">
          <DialogHeader>
            <DialogTitle>변경점 리스트</DialogTitle>
            <DialogDescription>
              {sensor.equipmentName} · {sensor.sensorName} · PPID_CHSTEP {sensor.chartStepCode}
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-2">
            {changePointItems.length ? (
              changePointItems.map((item) => (
                <div key={item.id} className="rounded-lg border bg-muted/30 px-3 py-2 text-sm">
                  <p className="font-semibold">{item.title}</p>
                  <p className="mt-1 text-xs leading-5 text-muted-foreground">{item.description}</p>
                </div>
              ))
            ) : (
              <div className="rounded-lg border bg-muted/30 px-3 py-6 text-center text-sm text-muted-foreground">
                표시할 변경점이 없습니다.
              </div>
            )}
          </div>
        </DialogContent>
      </Dialog>
    </>
  )
}

function FdcScatterGrid({ selectedStep, equipmentGroups, selectedSensorName }) {
  if (!selectedStep || !selectedSensorName) {
    return (
      <div className="flex h-72 items-center justify-center rounded-lg border bg-card text-sm text-muted-foreground">
        STEP과 FDC 센서를 선택하면 scatter chart가 표시됩니다.
      </div>
    )
  }

  if (!equipmentGroups.length) {
    return (
      <div className="flex h-72 items-center justify-center rounded-lg border bg-card text-sm text-muted-foreground">
        선택한 센서에 표시할 scatter chart가 없습니다.
      </div>
    )
  }

  return (
    <div className="grid gap-4">
      {equipmentGroups.map((group) => (
        <section
          key={group.equipmentId}
          className="grid gap-3 rounded-xl border bg-card p-3 shadow-sm"
          aria-label={`${group.equipmentName} 설비호기 chart 그룹`}
        >
          <div className="flex min-h-12 items-center justify-between gap-3 rounded-lg border bg-muted/50 px-4">
            <div className="min-w-0">
              <div className="mb-1 flex items-center gap-2">
                <Badge variant="outline" className="shrink-0">설비호기</Badge>
                <h3 className="truncate text-base font-semibold">{group.equipmentName}</h3>
              </div>
              <p className="truncate text-xs text-muted-foreground">
                {selectedSensorName} 기준으로 이 설비호기의 관련 chart를 표시합니다.
              </p>
            </div>
            <Badge variant="secondary" className="shrink-0">{group.sensors.length} charts</Badge>
          </div>
          <div className="grid grid-cols-2 gap-4 rounded-lg bg-muted/20 p-3">
            {group.sensors.map((sensor) => (
              <FdcScatterChart
                key={sensor.id}
                selectedStep={selectedStep}
                sensor={sensor}
                selected={sensor.sensorName === selectedSensorName}
              />
            ))}
          </div>
        </section>
      ))}
    </div>
  )
}

export function L0SpiderDashboardPage() {
  const pageRef = useRef(null)
  const [selectedLine, setSelectedLine] = useState(FDC_LINES[0])
  const teams = useMemo(() => getTeamsByLine(selectedLine), [selectedLine])
  const [selectedTeam, setSelectedTeam] = useState(teams[0] ?? "")
  const trendSteps = useMemo(
    () => getTrendSteps({ lineId: selectedLine, teamId: selectedTeam }),
    [selectedLine, selectedTeam],
  )
  const [selectedStepId, setSelectedStepId] = useState("")
  const [selectedSensorName, setSelectedSensorName] = useState("")
  const [selectedSensorGrades, setSelectedSensorGrades] = useState(() => ["A/B"])

  useEffect(() => {
    setSelectedTeam(teams[0] ?? "")
  }, [teams])

  useEffect(() => {
    setSelectedStepId(trendSteps[0]?.id ?? "")
    setSelectedSensorName("")
  }, [trendSteps])

  const selectedStep = trendSteps.find((step) => step.id === selectedStepId) ?? trendSteps[0]
  const stepSensorRecords = useMemo(() => {
    if (!selectedStep?.equipments?.length) return []
    const selectedGradeSet = new Set(selectedSensorGrades)

    return selectedStep.equipments.flatMap((equipment) =>
      equipment.sensors
        .filter((sensor) => selectedGradeSet.has(sensor.grade))
        .map((sensor) => ({
          ...sensor,
          equipmentId: equipment.id,
          equipmentName: equipment.equipmentName,
        })),
    )
  }, [selectedSensorGrades, selectedStep])
  const sensorOptions = useMemo(() => {
    const sensorsByName = new Map()

    stepSensorRecords.forEach((sensor) => {
      const current = sensorsByName.get(sensor.sensorName) ?? {
        id: sensor.sensorName,
        sensorName: sensor.sensorName,
        grade: sensor.grade,
        trendType: sensor.trendType,
        abnormalCount: 0,
        severity: 0,
        equipmentIds: new Set(),
        grades: new Set(),
      }

      current.abnormalCount += sensor.abnormalCount
      current.severity = Math.max(current.severity, sensor.severity)
      current.equipmentIds.add(sensor.equipmentId)
      current.grades.add(sensor.grade)
      sensorsByName.set(sensor.sensorName, current)
    })

    return Array.from(sensorsByName.values())
      .map((sensor) => ({
        ...sensor,
        grade: Array.from(sensor.grades).join(", "),
        equipmentCount: sensor.equipmentIds.size,
      }))
      .sort((a, b) => b.abnormalCount - a.abnormalCount || b.severity - a.severity)
  }, [stepSensorRecords])
  const selectedSensor = sensorOptions.find((sensor) => sensor.sensorName === selectedSensorName) ?? null
  const selectedEquipmentGroups = useMemo(() => {
    if (!selectedStep?.equipments?.length || !selectedSensorName) return []
    const selectedGradeSet = new Set(selectedSensorGrades)

    return selectedStep.equipments
      .map((equipment) => {
        const selectedSensor = equipment.sensors.find(
          (sensor) => sensor.sensorName === selectedSensorName && selectedGradeSet.has(sensor.grade),
        )

        return {
          equipmentId: equipment.id,
          equipmentName: equipment.equipmentName,
          sensors: selectedSensor
            ? buildSensorChartVariants({
                sensor: selectedSensor,
                selectedStep,
                equipmentId: equipment.id,
                equipmentName: equipment.equipmentName,
              })
            : [],
        }
      })
      .filter((group) => group.sensors.length > 0)
  }, [selectedSensorGrades, selectedSensorName, selectedStep])
  const selectedChartCount = selectedEquipmentGroups.reduce(
    (sum, group) => sum + group.sensors.length,
    0,
  )
  const handleSelectStep = (stepId) => {
    setSelectedStepId(stepId)
    setSelectedSensorName("")
  }
  const handleToggleSensorGrade = (grade) => {
    setSelectedSensorGrades((currentGrades) => {
      if (currentGrades.includes(grade)) {
        return currentGrades.filter((currentGrade) => currentGrade !== grade)
      }

      return SENSOR_GRADES.filter((currentGrade) => currentGrades.includes(currentGrade) || currentGrade === grade)
    })
  }
  const handleScrollToTop = () => {
    pageRef.current?.scrollTo({ top: 0, behavior: "smooth" })
  }

  useEffect(() => {
    if (!selectedSensorName) return
    if (sensorOptions.some((sensor) => sensor.sensorName === selectedSensorName)) return

    setSelectedSensorName("")
  }, [selectedSensorName, sensorOptions])

  return (
    <div ref={pageRef} className="relative flex h-full min-h-0 min-w-0 flex-col overflow-y-auto">
      <header className="shrink-0 border-b bg-card px-6 py-4">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <h1 className="text-2xl font-semibold tracking-tight">자설비 이상감지</h1>
              <Badge variant="outline">Screening</Badge>
            </div>
            <p className="text-sm text-muted-foreground">
              라인과 분임조를 선택해 선별된 이상 Trend를 스텝 기준으로 확인합니다.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Button type="button" variant="outline" size="sm" asChild>
              <Link to="/l0_spider">
                <ArrowLeft className="size-4" aria-hidden="true" />
                SPIDER 메인
              </Link>
            </Button>
            <Button type="button" variant="outline" size="sm">
              <BarChart3 className="size-4" aria-hidden="true" />
              Trend 기준 보기
            </Button>
          </div>
        </div>
      </header>

      <section className="grid shrink-0 gap-3 border-b bg-background px-6 py-4">
        <Tabs value={selectedLine} onValueChange={setSelectedLine}>
          <TabsList className="h-auto w-full flex-wrap justify-start gap-1 bg-muted/70">
            {FDC_LINES.map((lineId) => (
              <TabsTrigger key={lineId} value={lineId} className="h-8 flex-none px-3">
                {lineId}
              </TabsTrigger>
            ))}
          </TabsList>
        </Tabs>
        <Tabs value={selectedTeam} onValueChange={setSelectedTeam}>
          <TabsList className="h-auto w-full flex-wrap justify-start gap-1 bg-muted/70">
            {teams.map((teamId) => (
              <TabsTrigger key={teamId} value={teamId} className="h-8 flex-none px-3">
                {teamId}
              </TabsTrigger>
            ))}
          </TabsList>
        </Tabs>
        <div className="flex flex-wrap items-center gap-2">
          <span className="shrink-0 text-xs font-semibold text-muted-foreground">센서 등급</span>
          <div className="flex flex-wrap gap-1.5">
            {SENSOR_GRADES.map((grade) => (
              <SensorGradeButton
                key={grade}
                grade={grade}
                selected={selectedSensorGrades.includes(grade)}
                onToggle={() => handleToggleSensorGrade(grade)}
              />
            ))}
          </div>
        </div>
      </section>

      <main className="grid min-w-0 gap-5 px-6 pb-6 pt-5">
        <section className="grid h-[480px] w-full max-w-5xl min-w-0 grid-cols-[minmax(320px,420px)_minmax(380px,520px)] gap-4">
          <Card className="grid min-h-0 grid-rows-[48px_minmax(0,1fr)] gap-0 overflow-hidden rounded-xl border bg-card py-0 shadow-sm">
            <div className="flex h-12 items-center border-b bg-muted/40 px-4">
              <div className="flex h-full min-w-0 flex-1 items-center justify-between gap-3">
                <div className="min-w-0">
                  <CardTitle className="truncate text-sm font-semibold leading-5">STEP 선택</CardTitle>
                  <p className="truncate text-[11px] text-muted-foreground">이상 Trend가 많은 STEP 순서</p>
                </div>
                <Badge variant="secondary">{trendSteps.length} steps</Badge>
              </div>
            </div>
            <CardContent className="min-h-0 bg-background/60 p-2">
              {trendSteps.length === 0 ? (
                <div className="flex h-full min-h-32 items-center justify-center p-6 text-center text-sm text-muted-foreground">
                  선택한 분임조에 표시할 이상 Trend가 없습니다.
                </div>
              ) : (
                <div className="grid min-h-0 content-start gap-1.5 overflow-y-auto">
                  {trendSteps.map((step) => (
                    <TrendStepButton
                      key={step.id}
                      step={step}
                      selected={step.id === selectedStep?.id}
                      onSelect={() => handleSelectStep(step.id)}
                    />
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          <Card className="grid min-h-0 grid-rows-[48px_minmax(0,1fr)] gap-0 overflow-hidden rounded-xl border bg-card py-0 shadow-sm">
            <div className="flex h-12 items-center border-b bg-muted/40 px-4">
              <div className="flex h-full min-w-0 flex-1 items-center justify-between gap-3">
                <div className="min-w-0">
                  <CardTitle className="truncate text-sm font-semibold leading-5">
                    {selectedStep?.stepName ?? "STEP 미선택"}
                  </CardTitle>
                  <p className="truncate text-[11px] text-muted-foreground">선택 STEP에서 감지된 FDC 센서</p>
                </div>
                {selectedStep ? (
                  <Badge variant="secondary">{sensorOptions.length} sensors</Badge>
                ) : null}
              </div>
            </div>
            <CardContent className="min-h-0 bg-background/60 p-2">
              {sensorOptions.length ? (
                <div className="grid min-h-0 content-start gap-1.5 overflow-y-auto">
                  {sensorOptions.map((sensor) => (
                    <SensorButton
                      key={sensor.id}
                      sensor={sensor}
                      selected={sensor.sensorName === selectedSensor?.sensorName}
                      onSelect={() => setSelectedSensorName(sensor.sensorName)}
                    />
                  ))}
                </div>
              ) : (
                <div className="flex h-full min-h-32 items-center justify-center p-6 text-center text-sm text-muted-foreground">
                  STEP을 선택하면 FDC 센서가 표시됩니다.
                </div>
              )}
            </CardContent>
          </Card>
        </section>

        <section className="min-w-0">
          <div className="mb-3 flex items-center justify-between gap-3">
            <div className="min-w-0">
              <h2 className="truncate text-base font-semibold">Scatter chart</h2>
              <p className="mt-1 text-xs text-muted-foreground">
                FDC 센서 선택 후 설비호기별 카테고리로 chart를 2열 구조로 drawing합니다.
              </p>
            </div>
            {selectedSensor ? <Badge variant="secondary">{selectedChartCount} charts</Badge> : null}
          </div>
          <FdcScatterGrid
            selectedStep={selectedStep}
            equipmentGroups={selectedEquipmentGroups}
            selectedSensorName={selectedSensor?.sensorName}
          />
        </section>
      </main>
      <Button
        type="button"
        size="icon"
        className="fixed bottom-6 right-6 z-40 rounded-full shadow-lg"
        aria-label="화면 맨 위로 이동"
        onClick={handleScrollToTop}
      >
        <ArrowUp className="size-4" aria-hidden="true" />
      </Button>
    </div>
  )
}
