import { Activity, Gauge, RadioTower, Waves } from "lucide-react"

import { Card, CardContent } from "@/components/ui/card"

const ICONS = [Activity, Waves, Gauge, RadioTower]

export function PmKpiCards({ kpis }) {
  const rows = Array.isArray(kpis) ? kpis : []

  return (
    <section className="grid grid-cols-4 gap-4">
      {rows.map((kpi, index) => {
        const Icon = ICONS[index % ICONS.length]
        return (
          <Card key={kpi.key ?? kpi.label} className="rounded-lg py-0">
            <CardContent className="flex items-start justify-between gap-3 p-4">
              <div className="min-w-0">
                <p className="text-xs font-medium text-muted-foreground">{kpi.label}</p>
                <p className="mt-2 truncate text-2xl font-semibold tabular-nums tracking-tight">
                  {kpi.value}
                </p>
                <p className="mt-1 truncate text-xs text-muted-foreground">{kpi.detail}</p>
              </div>
              <span className="rounded-md border bg-muted p-2 text-muted-foreground">
                <Icon className="size-4" aria-hidden="true" />
              </span>
            </CardContent>
          </Card>
        )
      })}
    </section>
  )
}
