import { Activity, ArrowRight, Bug, Gauge, Lock, Network, Radar, ScanSearch } from "lucide-react"
import { Link } from "react-router-dom"

import { Badge } from "@/components/ui/badge"
import { hasAppAccess } from "@/lib/access/appAccess"
import { useAuth } from "@/lib/auth"

const spiderLinks = [
  {
    icon: Activity,
    title: "L0 Spider",
    description: "기존 L0 Spider 외부 화면으로 이동합니다.",
    href: "/spider/l0",
    badge: "L0",
    appScope: "l0-spider",
  },
  {
    icon: Radar,
    title: "L1 Spider",
    description: "기존 L1 Spider 외부 화면으로 이동합니다.",
    href: "/spider/l1",
    badge: "L1",
    appScope: "l1-spider",
  },
  {
    icon: Network,
    title: "L3 Spider",
    description: "L3 이상감지 Summary와 Chart 화면으로 이동합니다.",
    href: "/spider/l3",
    badge: "L3",
    appScope: "l3-spider",
  },
  {
    icon: ScanSearch,
    title: "TTTM Spider",
    description: "TTTM Spider 임베드 화면으로 이동합니다.",
    href: "/spider/tttm",
    badge: "TTTM",
    appScope: "tttm-spider",
  },
  {
    icon: Gauge,
    title: "PM Spider",
    description: "PM 기준 TRACE/OES 이상 패턴 조회 화면으로 이동합니다.",
    href: "/spider/pm",
    badge: "PM",
    appScope: "pm-spider",
  },
]

function SpiderLinkRow({ item, allowed }) {
  const Icon = item.icon
  const className = [
    "group relative flex min-w-0 items-center gap-4 overflow-hidden rounded-2xl border px-4 py-4 shadow-sm backdrop-blur transition-colors",
    allowed
      ? "border-border/80 bg-card/90 hover:border-destructive/40 hover:bg-card focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      : "cursor-not-allowed border-dashed border-border/70 bg-muted/40",
  ].join(" ")
  const iconClassName = [
    "relative z-10 flex size-11 shrink-0 items-center justify-center rounded-xl border bg-background/80 text-muted-foreground shadow-sm transition-colors",
    allowed ? "border-destructive/30 text-destructive group-hover:bg-destructive/10 group-hover:text-destructive" : "",
  ].join(" ")
  const content = (
    <>
      <span className="pointer-events-none absolute inset-y-0 left-0 w-1 bg-destructive/80 opacity-70 transition-opacity group-hover:opacity-100" aria-hidden="true" />
      <span className="pointer-events-none absolute -right-10 -top-12 size-28 rounded-full border border-primary/10" aria-hidden="true" />
      <span className={iconClassName}>
        <Icon className="size-5" aria-hidden="true" />
      </span>
      <span className="relative z-10 min-w-0 flex-1">
        <span className="flex min-w-0 flex-wrap items-center gap-2">
          <span className="truncate text-base font-semibold text-foreground">{item.title}</span>
          <Badge variant="secondary" className="shrink-0 border border-border/60 bg-primary/10 text-foreground">
            {item.badge}
          </Badge>
          {!allowed ? (
            <Badge variant="outline" className="shrink-0 border-destructive/40 text-destructive">
              권한 없음
            </Badge>
          ) : null}
        </span>
        <span className="mt-1 block truncate text-sm text-muted-foreground">{item.description}</span>
      </span>
      {allowed ? (
        <ArrowRight className="relative z-10 size-4 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-0.5 group-hover:text-destructive" aria-hidden="true" />
      ) : (
        <Lock className="relative z-10 size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
      )}
    </>
  )

  return (
    <li>
      {allowed ? (
        <Link to={item.href} className={className}>
          {content}
        </Link>
      ) : (
        <div className={className} aria-disabled="true">
          {content}
        </div>
      )}
    </li>
  )
}

function SpiderWebBackdrop() {
  const webLines = [
    "rotate-0",
    "rotate-30",
    "rotate-60",
    "rotate-90",
    "rotate-120",
    "rotate-150",
  ]

  return (
    <div className="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden="true">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_18%_12%,var(--destructive)_0,transparent_28%),radial-gradient(circle_at_84%_18%,var(--primary)_0,transparent_24%),linear-gradient(135deg,var(--background),var(--muted))] opacity-[0.13]" />
      <div className="absolute -left-32 -top-36 size-[34rem] opacity-45">
        <div className="absolute inset-0 rounded-full border border-destructive/25" />
        <div className="absolute inset-16 rounded-full border border-destructive/20" />
        <div className="absolute inset-32 rounded-full border border-destructive/15" />
        <div className="absolute left-1/2 top-1/2 size-3 -translate-x-1/2 -translate-y-1/2 rounded-full bg-destructive/50" />
        {webLines.map((line) => (
          <span
            key={line}
            className={`absolute left-1/2 top-1/2 h-px w-[34rem] origin-left bg-destructive/20 ${line}`}
          />
        ))}
      </div>
      <div className="absolute -bottom-44 -right-28 size-[38rem] opacity-35">
        <div className="absolute inset-0 rounded-full border border-primary/25" />
        <div className="absolute inset-20 rounded-full border border-primary/20" />
        <div className="absolute inset-40 rounded-full border border-primary/15" />
        {webLines.map((line) => (
          <span
            key={line}
            className={`absolute left-1/2 top-1/2 h-px w-[38rem] origin-left bg-primary/20 ${line}`}
          />
        ))}
      </div>
      <div className="absolute inset-x-0 top-0 h-24 bg-gradient-to-b from-background to-transparent" />
    </div>
  )
}

export function SpiderHomePage() {
  const { user } = useAuth()

  return (
    <div className="relative flex h-full min-h-0 min-w-0 flex-col overflow-hidden bg-background">
      <SpiderWebBackdrop />
      <main className="relative z-10 min-h-0 flex-1 overflow-y-auto px-6 py-8">
        <div className="mx-auto grid w-full max-w-6xl gap-6 lg:grid-cols-[minmax(0,1fr),28rem]">
          <header className="flex min-h-[12rem] flex-col justify-between overflow-hidden rounded-2xl border border-border/80 p-6 shadow-sm backdrop-blur">
            <div className="space-y-5">
              <Badge variant="outline" className="w-fit border-destructive/40 bg-destructive/10 text-destructive">
                Spider Main
              </Badge>
              <div className="space-y-4">
                <div className="flex items-center gap-3">
                  <span className="flex size-14 shrink-0 items-center justify-center rounded-2xl border border-destructive/30 bg-destructive/10 text-destructive shadow-sm">
                    <Bug className="size-7" aria-hidden="true" />
                  </span>
                  <h1 className="text-2xl font-semibold tracking-tight text-foreground">SPIDER</h1>
                </div>
                <p className="max-w-xl text-sm leading-6 text-muted-foreground">
                  스파이더 웹처럼 연결된 분석 화면 중 접속할 Spider를 선택하세요.
                </p>
              </div>
            </div>
          </header>

          <section aria-labelledby="spider-link-list-title" className="grid min-w-0 gap-3">
            <div className="flex items-center justify-between gap-3">
              <h2 id="spider-link-list-title" className="text-base font-semibold">
                Spider 링크
              </h2>
              <Badge variant="secondary" className="border border-border/60 bg-card/90">
                {spiderLinks.length} Apps
              </Badge>
            </div>
            <ul className="grid gap-3">
              {spiderLinks.map((item) => (
                <SpiderLinkRow
                  key={item.title}
                  item={item}
                  allowed={hasAppAccess(user, item.appScope)}
                />
              ))}
            </ul>
          </section>
        </div>
      </main>
    </div>
  )
}
