export const FDC_LINES = Object.freeze([
  "H1L",
  "15L",
  "16L",
  "17L",
  "P1F",
  "P1D",
  "P23F",
  "P2D",
  "P3D",
  "P3D2",
])

export const SPIDER_LINE_REV = Object.freeze({
  Lambda_H1L: "H1L",
  Dreams_H1L: "H1L",
  TERA_H1L: "H1L",
  Lambda_15L: "15L",
  Dreams_15L: "15L",
  TERA_15L: "15L",
  Lambda_16L: "16L",
  Dreams_16L: "16L",
  TERA_16L: "16L",
  Lambda_17L: "17L",
  Dreams_17L: "17L",
  TERA_17L: "17L",
  Lambda_P1D: "P1D",
  Dreams_P1D: "P1D",
  TERA_P1D: "P1D",
  Lambda_P1F: "P1F",
  Dreams_P1F: "P1F",
  TERA_P1F: "P1F",
  Lambda_P23F: "P23F",
  Dreams_P23F: "P23F",
  TERA_P23F: "P23F",
  Lambda_P2D: "P2D",
  Dreams_P2D: "P2D",
  TERA_P2D: "P2D",
  Lambda_P3D: "P3D",
  Dreams_P3D: "P3D",
  TERA_P3D: "P3D",
  Lambda_P3D2: "P3D2",
  Dreams_P3D2: "P3D2",
  TERA_P3D2: "P3D2",
  Lambda_U: "EndFab",
  Dreams_U: "EndFab",
  TERA_U: "EndFab",
})

const LINE_TEAMS = Object.freeze(
  FDC_LINES.reduce((lines, lineId) => {
    lines[lineId] = Object.entries(SPIDER_LINE_REV)
      .filter(([, mappedLineId]) => mappedLineId === lineId)
      .map(([sdwt]) => sdwt)
    return lines
  }, {}),
)

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
export const SENSOR_GRADES = Object.freeze(["A/B", "D", "N", "M"])
export const SPIDER_FILE_PATHS = Object.freeze({
  dbInfo: "db_info.pkl",
  dataRoot: "/appdata/abnormal_trend/pic/",
  erdRoot: "/appdata/abnormal_trend/pic/erd",
  commonDate: "/appdata/abnormal_trend/pic/common_date.txt",
  commonalityRoot: "/appdata/abnormal_trend/pic/erd_commonality",
  latestPath: "/appdata/abnormal_trend/pic/path/2026-05-29",
  latestStats: "/appdata/abnormal_trend/pic/stats/2026-05-29_spider_step_stats_except_v.parquets",
  hardSpecRoot: "/appdata/erd_stats_commonality/H1L",
  priority: "/appdata/abnormal_trend/pic/priority/priority.parquet",
  unitModel: "/appdata/abnormal_trend/pic/unit_model.parquet",
  hardLimit: "/appdata/abnormal_trend/pic/HARD_LIMIT.parquet",
  hardSpecImage: "/appdata/abnormal_trend/pic/recommand_spec.png",
  manualImage: "/appdata/abnormal_trend/code/manual.png",
  yieldRoot: "/appdata/abnormal_trend/pic/yh/P1F_CHH",
  yieldImage: "/appdata/abnormal_trend/pic/yh/P1F_CHH/yh_desc.png",
  hardSpecChartRoot: "/appdata/abnormal_trend/pic/erd_hard_spec",
  hardSpecServerChartRoot: "/appdata/abnormal_trend/pic_server2/erd_hard_spec",
  mErdRoot: "/appdata/m_erdtsum_data_agg",
  backupRoot: "/appdata/abnormal_trend/pic/backup/",
})
const LINE_FACTORS = Object.freeze(Object.fromEntries(FDC_LINES.map((lineId, index) => [lineId, index])))

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
    grade: SENSOR_GRADES[(sensorSeed + stepIndex + equipmentIndex) % SENSOR_GRADES.length],
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

export function getSpiderSummaryRows() {
  const lineRows = FDC_LINES.map((lineId, index) => {
    const ng = 18 + index * 7
    const ok = 460 + index * 64

    return {
      line_id: lineId,
      "A등급": 4 + index,
      "B등급": 7 + index * 2,
      "D등급": 9 + index,
      "M등급": 3 + (index % 4),
      "N등급": 8 + index * 3,
      OK: ok,
      NG: ng,
      "NG비율": `${((ng / (ok + ng)) * 100).toFixed(2)}%`,
    }
  })

  const sdwtRows = lineRows.flatMap((line, lineIndex) =>
    ["Lambda", "Dreams", "TERA"].map((prefix, teamIndex) => {
      const ng = Math.max(3, Math.round(line.NG / (teamIndex + 2)))
      const ok = Math.round(line.OK / (teamIndex + 1.8))

      return {
        sdwt: `${prefix}_${line.line_id}`,
        "A등급": Math.max(1, line["A등급"] - teamIndex),
        "B등급": Math.max(1, line["B등급"] - teamIndex),
        "D등급": Math.max(1, line["D등급"] - teamIndex),
        "M등급": Math.max(0, line["M등급"] - teamIndex),
        "N등급": Math.max(1, line["N등급"] - teamIndex),
        OK: ok,
        NG: ng + lineIndex,
        "NG비율": `${(((ng + lineIndex) / (ok + ng + lineIndex)) * 100).toFixed(2)}%`,
      }
    }),
  )

  return { lineRows, sdwtRows }
}

export function getSpiderAnomalyRows() {
  const date = "2026-05-29"

  return FDC_LINES.flatMap((lineId, lineIndex) =>
    getTeamsByLine(lineId).flatMap((teamId, teamIndex) =>
      getTrendSteps({ lineId, teamId }).slice(0, 10).flatMap((step, stepIndex) =>
        step.equipments.slice(0, 3).flatMap((equipment) =>
          equipment.sensors.slice(0, 2).map((sensor, sensorIndex) => {
            const sensorPath = sensor.sensorName.replaceAll(" ", "_")
            const eqpFile = `${equipment.equipmentName}.png`
            const recipeOffset = lineIndex * 300 + teamIndex * 70 + stepIndex * 17

            return {
              id: `${step.id}-${equipment.id}-${sensorIndex}`,
              line_id: lineId,
              sdwt: teamId,
              desc: step.stepName,
              ver: `V${1 + (stepIndex % 3)}`,
              recipe_id: `RCP-${4100 + recipeOffset}`,
              date,
              grade: sensor.grade,
              sensor: sensor.sensorName,
              eqp: eqpFile,
              file_path: `${SPIDER_FILE_PATHS.dataRoot}erd/${date}/${teamId}/${step.stepName}/${sensor.grade}/${sensorPath}/${eqpFile}`,
              abnormalCount: sensor.abnormalCount,
              latestAt: sensor.latestAt,
              points: sensor.points,
            }
          }),
        ),
      ),
    ),
  )
}

export function getSpiderCommonalityRows() {
  return getSpiderAnomalyRows().map((row, index) => ({
    ...row,
    priority: index % 2 === 0 ? "A(c)" : "B(c)",
    step_seq: `CR${380250 + index * 100}`,
    step_desc: row.desc,
    ppid: `PPID-${720 + index}`,
    recipe_id: row.recipe_id,
    ch_step: `${1200 + index * 7}@001`,
    file_path: `${SPIDER_FILE_PATHS.commonalityRoot}/2026-05-29/${row.sdwt}/${index % 2 === 0 ? "A(c)" : "B(c)"}/${row.desc}/${row.recipe_id}/${row.sensor.replaceAll(" ", "_")}_T/${1200 + index * 7}@001/img.png`,
  }))
}

export function getSpiderHistoryRows() {
  return getSpiderAnomalyRows().slice(0, 8).map((row, index) => ({
    id: `history-${row.id}`,
    update_date: `2026-05-${String(22 + (index % 7)).padStart(2, "0")}`,
    line_id: row.line_id,
    sdwt: row.sdwt,
    file_path: row.file_path.replace("/pic/", "/pic/backup/"),
    sensor: row.sensor,
    eqp: row.eqp.replace(".png", ""),
  }))
}

export function getHardSpecRows() {
  return getSpiderAnomalyRows().slice(0, 14).map((row, index) => {
    const lower = 42 + index * 0.8
    const upper = lower + 18 + (index % 5)
    const hardLower = lower - 6 - (index % 3)
    const hardUpper = upper + 9 + (index % 4)
    const ratio = (hardUpper - hardLower) / (upper - lower)

    return {
      id: `hard-${row.id}`,
      priority: index % 2 === 0 ? "A" : "B",
      sensor_name: row.sensor,
      ch_step: `${1200 + index * 7}@001`,
      "추천Spec(Lower)": Number(lower.toFixed(2)),
      "추천Spec(Upper)": Number(upper.toFixed(2)),
      "기존Spec(Lower)": Number(hardLower.toFixed(2)),
      "기존Spec(Upper)": Number(hardUpper.toFixed(2)),
      "Spec격차": `${ratio.toFixed(1)}배`,
      source_path: `${SPIDER_FILE_PATHS.hardSpecRoot}/Dreams_H1L/${1200 + index * 7}/PPID-${720 + index}/${row.recipe_id}/2026-05-29`,
    }
  })
}

export function getYieldSpecRows(stepSeq = "CR380250") {
  return SENSOR_NAMES.map((sensor, index) => ({
    id: `${stepSeq}-${sensor}`,
    step_seq: stepSeq,
    recipe_id: `PPID_${740 + index}`,
    fdc_parameter: sensor,
    g_min: Number((42 + index * 1.4).toFixed(2)),
    g_max: Number((61 + index * 1.6).toFixed(2)),
    b_min: Number((38 + index * 1.1).toFixed(2)),
    b_max: Number((69 + index * 1.9).toFixed(2)),
    source_path: `${SPIDER_FILE_PATHS.yieldRoot}/${stepSeq}_PPID_${740 + index}.csv`,
  }))
}

export function getRecipientRows() {
  return [
    {
      email: "t1232.kang",
      sdwt: "['Lambda_H1L', 'Dreams_H1L']",
      priority: "['A', 'B', 'D']",
    },
    {
      email: "etch.user",
      sdwt: "['TERA_H1L']",
      priority: "['A', 'B', 'D', 'M', 'N']",
    },
  ]
}
