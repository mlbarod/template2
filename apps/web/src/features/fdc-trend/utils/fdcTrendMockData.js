export const FDC_LINES = Object.freeze([
  "H1",
  "15L",
  "16L",
  "17L",
  "P1D",
  "P1F",
  "P2D",
  "P23F",
  "P3D",
  "P3D2",
  "EndFab",
])

const LINE_TEAMS = Object.freeze({
  H1: ["H1-A", "H1-B", "H1-C"],
  "15L": ["15L-A", "15L-B"],
  "16L": ["16L-A", "16L-B", "16L-C"],
  "17L": ["17L-A", "17L-B"],
  P1D: ["P1D-Etch", "P1D-CVD", "P1D-Diff"],
  P1F: ["P1F-CMP", "P1F-Metal"],
  P2D: ["P2D-Photo", "P2D-Implant"],
  P23F: ["P23F-CVD", "P23F-Wet", "P23F-Metal"],
  P3D: ["P3D-Etch", "P3D-Photo"],
  P3D2: ["P3D2-CMP", "P3D2-Wet"],
  EndFab: ["EndFab-Final", "EndFab-Pack"],
})

const STEP_NAMES = [
  "1.0 MASK ETCH",
  "1.1 MAIN ETCH",
  "1.2 OVER ETCH",
  "2.0 POLY ETCH",
  "2.1 CONTACT ETCH",
  "3.0 OXIDE ETCH",
  "3.1 CHAMBER CLEAN",
  "4.0 ASH STRIP",
]

const SENSOR_NAMES = [
  "ESC Voltage",
  "RF Forward Power",
  "Chamber Pressure",
  "He Backside Flow",
  "Gas Flow Ratio",
  "Bias Voltage",
  "Endpoint Intensity",
  "Chuck Temperature",
]

const TOOL_GROUPS = ["EQC-01", "EQC-02", "EQC-03", "EQC-04"]
const TREND_TYPES = ["upper-shift", "variance", "cluster", "drift"]
const LINE_FACTORS = Object.freeze({
  H1: 0,
  "15L": 1,
  "16L": 2,
  "17L": 3,
  P1D: 4,
  P1F: 5,
  P2D: 6,
  P23F: 7,
  P3D: 8,
  P3D2: 9,
  EndFab: 10,
})

function getLineFactor(lineId) {
  return LINE_FACTORS[lineId] ?? 0
}

function buildPoints(seed, severity) {
  return Array.from({ length: 28 }, (_, index) => {
    const phase = index + seed
    const base = 52 + Math.sin(phase / 2.4) * 5 + seed * 0.7
    const trend = Math.max(0, index - 14) * (severity / 24)
    const spike = index % 9 === seed % 5 ? severity * 0.42 : 0
    const value = Number((base + trend + spike).toFixed(2))
    const limit = 60 + severity * 0.26

    return {
      wafer: `W${String(index + 1).padStart(2, "0")}`,
      lot: `LOT-${seed}${String(index + 7).padStart(2, "0")}`,
      time: `${String(Math.floor(index / 2)).padStart(2, "0")}:${index % 2 === 0 ? "00" : "30"}`,
      value,
      limit: Number(limit.toFixed(2)),
      status: value > limit ? "abnormal" : "normal",
    }
  })
}

function buildEquipmentId(seed, equipmentIndex) {
  const toolNumber = 120 + ((seed * 13 + equipmentIndex * 17) % 760)
  const chamberNumber = 1 + ((seed + equipmentIndex) % 4)

  return `ELPP${String(toolNumber).padStart(3, "0")}-${chamberNumber}`
}

function buildSensorRecord({ stepId, equipmentId, stepIndex, equipmentIndex, sensorIndex, seed }) {
  const sensorSeed = seed + equipmentIndex * 5 + sensorIndex * 3
  const severity = 56 + ((sensorSeed * 11 + stepIndex * 5) % 38)
  const points = buildPoints(sensorSeed, severity)
  const abnormalCount = points.filter((point) => point.status === "abnormal").length

  return {
    id: `${stepId}-${equipmentId}-sensor-${sensorIndex}`,
    sensorName: SENSOR_NAMES[(stepIndex + equipmentIndex + sensorIndex + seed) % SENSOR_NAMES.length],
    trendType: TREND_TYPES[(sensorSeed + stepIndex) % TREND_TYPES.length],
    severity,
    abnormalCount,
    latestAt: `2026-05-${String(24 + ((sensorSeed + stepIndex) % 5)).padStart(2, "0")} ${String(8 + (sensorSeed % 9)).padStart(2, "0")}:30`,
    points,
  }
}

function buildEquipmentRecord({ stepId, stepIndex, equipmentIndex, seed }) {
  const equipmentId = buildEquipmentId(seed + stepIndex, equipmentIndex)
  const sensorCount = 3 + ((seed + stepIndex + equipmentIndex) % 3)
  const sensors = Array.from({ length: sensorCount }, (_, sensorIndex) =>
    buildSensorRecord({ stepId, equipmentId, stepIndex, equipmentIndex, sensorIndex, seed }),
  ).sort((a, b) => b.abnormalCount - a.abnormalCount || b.severity - a.severity)
  const abnormalCount = sensors.reduce((sum, sensor) => sum + sensor.abnormalCount, 0)
  const severity = sensors.length
    ? Math.max(...sensors.map((sensor) => sensor.severity))
    : 0

  return {
    id: equipmentId,
    equipmentId,
    equipmentName: equipmentId,
    severity,
    abnormalCount,
    sensorCount,
    latestAt: sensors[0]?.latestAt ?? `2026-05-${String(24 + ((seed + stepIndex) % 5)).padStart(2, "0")} ${String(8 + (seed % 9)).padStart(2, "0")}:30`,
    sensors,
  }
}

function buildStepRecord({ lineId, teamId, stepIndex, teamIndex }) {
  const seed = getLineFactor(lineId) + teamIndex + stepIndex + 1
  const stepId = `${lineId}-${teamId}-${stepIndex}`
  const equipmentCount = 3 + ((seed + stepIndex) % 4)
  const equipments = Array.from({ length: equipmentCount }, (_, equipmentIndex) =>
    buildEquipmentRecord({ stepId, stepIndex, equipmentIndex, seed }),
  ).sort((a, b) => b.abnormalCount - a.abnormalCount || b.severity - a.severity)
  const sensors = equipments.flatMap((equipment) => equipment.sensors)
  const abnormalCount = equipments.reduce((sum, equipment) => sum + equipment.abnormalCount, 0)
  const severity = equipments.length
    ? Math.max(...equipments.map((equipment) => equipment.severity))
    : 0

  return {
    id: stepId,
    lineId,
    teamId,
    stepName: STEP_NAMES[(stepIndex + seed) % STEP_NAMES.length],
    stepCode: `STEP-${String(1200 + seed * 17).padStart(4, "0")}`,
    toolGroup: TOOL_GROUPS[(stepIndex + teamIndex) % TOOL_GROUPS.length],
    trendType: sensors[0]?.trendType ?? TREND_TYPES[(seed + stepIndex) % TREND_TYPES.length],
    severity,
    abnormalCount,
    equipmentCount,
    sensorCount: sensors.length,
    lotCount: 18 + ((seed + stepIndex) % 9),
    latestAt: sensors[0]?.latestAt ?? `2026-05-${String(24 + ((seed + stepIndex) % 5)).padStart(2, "0")} ${String(8 + (seed % 9)).padStart(2, "0")}:30`,
    equipments,
    sensors,
    points: sensors[0]?.points ?? [],
  }
}

export function getTeamsByLine(lineId) {
  return LINE_TEAMS[lineId] ?? []
}

export function getTrendSteps({ lineId, teamId }) {
  const teams = getTeamsByLine(lineId)
  const teamIndex = Math.max(0, teams.indexOf(teamId))
  const stepCount = 15

  return Array.from({ length: stepCount }, (_, stepIndex) =>
    buildStepRecord({ lineId, teamId, stepIndex, teamIndex }),
  ).sort((a, b) => b.severity - a.severity)
}

export function getSeverityLabel(severity) {
  if (severity >= 82) return "High"
  if (severity >= 70) return "Watch"
  return "Review"
}
