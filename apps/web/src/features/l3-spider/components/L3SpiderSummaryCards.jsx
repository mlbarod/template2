import { Activity, AlertTriangle, Gauge } from "lucide-react"

import { formatNumber } from "../utils/format"

const STAT_CARDS = [
  {
    key: "anomalySteps",
    label: "Anomaly Steps",
    icon: AlertTriangle,
    className: "text-chart-4",
  },
  {
    key: "highRiskEqpchs",
    label: "High Risk EQPCH",
    icon: Activity,
    className: "text-destructive",
  },
  {
    key: "total",
    label: "Total Rows",
    icon: Gauge,
    className: "text-foreground",
  },
]

export function L3SpiderSummaryCards({ stats }) {
  return (
    <section
      className="flex shrink-0 items-center gap-0 border-b bg-card px-6"
      aria-label="L3 Spider 요약"
    >
      {STAT_CARDS.map(({ key, label, icon: Icon, className }) => (
        <div
          key={key}
          className="flex items-center gap-3 border-r px-6 py-3 first:pl-0 last:border-r-0"
        >
          <Icon className={`size-4 shrink-0 ${className}`} aria-hidden="true" />
          <div className="min-w-0">
            <p className={`text-xl font-semibold leading-none tabular-nums ${className}`}>
              {formatNumber(stats?.[key])}
            </p>
            <p className="mt-1 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
              {label}
            </p>
          </div>
        </div>
      ))}
    </section>
  )
}
