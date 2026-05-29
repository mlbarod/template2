import { useEffect, useMemo, useState } from "react"
import {
  BarChart3,
  ChevronRight,
} from "lucide-react"
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
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { cn } from "@/lib/utils"

import {
  FDC_LINES,
  getTeamsByLine,
  getTrendSteps,
} from "../utils/fdcTrendMockData"

const TREND_TYPE_LABELS = {
  "upper-shift": "상한 이동",
  variance: "분산 확대",
  cluster: "군집 이상",
  drift: "점진 Drift",
}

function formatTrendType(value) {
  return TREND_TYPE_LABELS[value] ?? value
}

function TrendStepButton({ step, selected, onSelect }) {
  return (
    <button
      type="button"
      onClick={onSelect}
      className={cn(
        "flex h-7 w-full min-w-0 items-center justify-between gap-3 border-b px-3 text-left text-xs transition last:border-b-0 hover:bg-muted/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring",
        selected && "bg-accent text-accent-foreground",
      )}
    >
      <span className="min-w-0 flex-1 truncate font-semibold">{step.stepName}</span>
      <span className="shrink-0 text-muted-foreground">{step.equipmentCount}대</span>
      <span className="min-w-12 shrink-0 text-right font-semibold tabular-nums">
        {step.abnormalCount}건수
      </span>
      <span className="shrink-0 text-muted-foreground">
        <ChevronRight className="size-3" aria-hidden="true" />
      </span>
    </button>
  )
}

function EquipmentButton({ equipment, selected, onSelect }) {
  return (
    <button
      type="button"
      onClick={onSelect}
      className={cn(
        "flex min-w-0 items-center justify-between gap-3 border-b px-4 py-2 text-left transition last:border-b-0 hover:bg-muted/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring",
        selected && "bg-accent text-accent-foreground",
      )}
    >
      <span className="min-w-0">
        <span className="block truncate text-sm font-semibold">{equipment.equipmentName}</span>
        <span className="mt-1 block text-xs text-muted-foreground">{equipment.sensorCount} sensors</span>
      </span>
      <span className="min-w-14 shrink-0 text-right text-sm font-semibold tabular-nums">
        {equipment.abnormalCount}건수
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
        "flex min-w-0 items-center justify-between gap-3 border-b px-4 py-2 text-left transition last:border-b-0 hover:bg-muted/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring",
        selected && "bg-accent text-accent-foreground",
      )}
    >
      <span className="min-w-0">
        <span className="block truncate text-sm font-semibold">{sensor.sensorName}</span>
        <span className="mt-1 block text-xs text-muted-foreground">{formatTrendType(sensor.trendType)}</span>
      </span>
      <span className="min-w-14 shrink-0 text-right text-sm font-semibold tabular-nums">
        {sensor.abnormalCount}건수
      </span>
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
  if (!selectedStep || !sensor) {
    return (
      <div className="flex h-72 items-center justify-center rounded-lg border bg-card text-sm text-muted-foreground">
        STEP, 설비호기, FDC 센서를 선택하면 scatter chart가 표시됩니다.
      </div>
    )
  }

  return (
    <div
      className={cn(
        "grid h-[320px] min-h-0 grid-rows-[40px_minmax(0,1fr)_44px] gap-0 rounded-lg border bg-card",
        selected && "border-primary",
      )}
    >
      <div className="min-w-0 border-b bg-muted/60 px-2 py-1">
        <h3 className="truncate text-xs font-semibold leading-4">{sensor.sensorName}</h3>
        <p className="truncate text-[11px] leading-4 text-muted-foreground">
          PPID_CHSTEP: {selectedStep.stepCode}_{selectedStep.stepName}
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
        <Button type="button" variant="outline" size="sm" className="h-8 min-w-0 px-1 text-xs">
          동일성차트
        </Button>
        <Button type="button" variant="outline" size="sm" className="h-8 min-w-0 px-1 text-xs">
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
  )
}

function FdcScatterGrid({ selectedStep, selectedEquipment, sensors, selectedSensorId }) {
  if (!selectedStep || !selectedEquipment || !selectedSensorId) {
    return (
      <div className="flex h-72 items-center justify-center rounded-lg border bg-card text-sm text-muted-foreground">
        STEP, 설비호기, FDC 센서를 선택하면 scatter chart가 표시됩니다.
      </div>
    )
  }

  if (!sensors.length) {
    return (
      <div className="flex h-72 items-center justify-center rounded-lg border bg-card text-sm text-muted-foreground">
        선택한 설비호기에 표시할 scatter chart가 없습니다.
      </div>
    )
  }

  return (
    <div className="grid grid-cols-2 gap-4">
      {sensors.map((sensor) => (
        <FdcScatterChart
          key={sensor.id}
          selectedStep={selectedStep}
          sensor={sensor}
          selected={sensor.id === selectedSensorId}
        />
      ))}
    </div>
  )
}

export function FdcTrendPage() {
  const [selectedLine, setSelectedLine] = useState(FDC_LINES[0])
  const teams = useMemo(() => getTeamsByLine(selectedLine), [selectedLine])
  const [selectedTeam, setSelectedTeam] = useState(teams[0] ?? "")
  const trendSteps = useMemo(
    () => getTrendSteps({ lineId: selectedLine, teamId: selectedTeam }),
    [selectedLine, selectedTeam],
  )
  const [selectedStepId, setSelectedStepId] = useState("")
  const [selectedEquipmentId, setSelectedEquipmentId] = useState("")
  const [selectedSensorId, setSelectedSensorId] = useState("")

  useEffect(() => {
    setSelectedTeam(teams[0] ?? "")
  }, [teams])

  useEffect(() => {
    setSelectedStepId(trendSteps[0]?.id ?? "")
    setSelectedEquipmentId("")
    setSelectedSensorId("")
  }, [trendSteps])

  const selectedStep = trendSteps.find((step) => step.id === selectedStepId) ?? trendSteps[0]
  const selectedEquipment = selectedStep?.equipments?.find((equipment) => equipment.id === selectedEquipmentId) ?? null
  const selectedSensors = selectedEquipment?.sensors ?? []
  const selectedSensor = selectedSensors.find((sensor) => sensor.id === selectedSensorId) ?? null
  const handleSelectStep = (stepId) => {
    setSelectedStepId(stepId)
    setSelectedEquipmentId("")
    setSelectedSensorId("")
  }
  const handleSelectEquipment = (equipmentId) => {
    setSelectedEquipmentId(equipmentId)
    setSelectedSensorId("")
  }

  return (
    <div className="flex h-full min-h-0 min-w-0 flex-col overflow-y-auto">
      <header className="shrink-0 border-b bg-card px-6 py-4">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <h1 className="text-2xl font-semibold tracking-tight">L0 Spider</h1>
              <Badge variant="outline">Screening</Badge>
            </div>
            <p className="text-sm text-muted-foreground">
              라인과 분임조를 선택해 선별된 이상 Trend를 스텝 기준으로 확인합니다.
            </p>
          </div>
          <Button type="button" variant="outline" size="sm">
            <BarChart3 className="size-4" aria-hidden="true" />
            Trend 기준 보기
          </Button>
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
      </section>

      <main className="grid min-w-0 gap-4 px-6 pb-6 pt-4">
        <section className="grid h-[520px] min-w-0 grid-cols-3 gap-4">
          <Card className="grid min-h-0 grid-rows-[40px_minmax(0,1fr)] gap-0 overflow-hidden rounded-lg py-0 shadow-none">
            <div className="flex h-10 items-center border-b bg-muted/60 px-2">
              <div className="flex h-full min-w-0 items-center justify-between gap-3">
                <div className="min-w-0">
                  <CardTitle className="truncate text-sm leading-4">STEP 선택</CardTitle>
                </div>
                <Badge variant="secondary">{trendSteps.length} steps</Badge>
              </div>
            </div>
            <CardContent className="min-h-0 p-0">
              {trendSteps.length === 0 ? (
                <div className="flex h-full min-h-32 items-center justify-center p-6 text-center text-sm text-muted-foreground">
                  선택한 분임조에 표시할 이상 Trend가 없습니다.
                </div>
              ) : (
                <div className="grid min-h-0 overflow-y-auto">
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

          <Card className="grid min-h-0 grid-rows-[40px_minmax(0,1fr)] gap-0 overflow-hidden rounded-lg py-0 shadow-none">
            <div className="flex h-10 items-center border-b bg-muted/60 px-2">
              <div className="flex h-full min-w-0 items-center justify-between gap-3">
                <div className="min-w-0">
                  <CardTitle className="truncate text-sm leading-4">
                    {selectedStep?.stepName ?? "STEP 미선택"}
                  </CardTitle>
                </div>
                {selectedStep ? (
                  <Badge variant="secondary">{selectedStep.equipmentCount}대</Badge>
                ) : null}
              </div>
            </div>
            <CardContent className="min-h-0 p-0">
              {selectedStep?.equipments?.length ? (
                <div className="grid min-h-0 overflow-y-auto">
                  {selectedStep.equipments.map((equipment) => (
                    <EquipmentButton
                      key={equipment.id}
                      equipment={equipment}
                      selected={equipment.id === selectedEquipment?.id}
                      onSelect={() => handleSelectEquipment(equipment.id)}
                    />
                  ))}
                </div>
              ) : (
                <div className="flex h-full min-h-32 items-center justify-center p-6 text-center text-sm text-muted-foreground">
                  선택한 STEP에 표시할 설비호기가 없습니다.
                </div>
              )}
            </CardContent>
          </Card>

          <Card className="grid min-h-0 grid-rows-[40px_minmax(0,1fr)] gap-0 overflow-hidden rounded-lg py-0 shadow-none">
            <div className="flex h-10 items-center border-b bg-muted/60 px-2">
              <div className="flex h-full min-w-0 items-center justify-between gap-3">
                <div className="min-w-0">
                  <CardTitle className="truncate text-sm leading-4">
                    {selectedEquipment?.equipmentName ?? "설비호기 미선택"}
                  </CardTitle>
                </div>
                {selectedEquipment ? (
                  <Badge variant="secondary">{selectedEquipment.abnormalCount}건수</Badge>
                ) : null}
              </div>
            </div>
            <CardContent className="min-h-0 p-0">
              {selectedSensors.length ? (
                <div className="grid min-h-0 overflow-y-auto">
                  {selectedSensors.map((sensor) => (
                    <SensorButton
                      key={sensor.id}
                      sensor={sensor}
                      selected={sensor.id === selectedSensor?.id}
                      onSelect={() => setSelectedSensorId(sensor.id)}
                    />
                  ))}
                </div>
              ) : (
                <div className="flex h-full min-h-32 items-center justify-center p-6 text-center text-sm text-muted-foreground">
                  설비호기를 선택하면 FDC 센서가 표시됩니다.
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
                FDC 센서 선택 후 선택한 설비호기의 chart를 2열 구조로 drawing합니다.
              </p>
            </div>
            {selectedSensor ? <Badge variant="secondary">{selectedSensors.length} charts</Badge> : null}
          </div>
          <FdcScatterGrid
            selectedStep={selectedStep}
            selectedEquipment={selectedEquipment}
            sensors={selectedSensor ? selectedSensors : []}
            selectedSensorId={selectedSensor?.id}
          />
        </section>
      </main>
    </div>
  )
}
