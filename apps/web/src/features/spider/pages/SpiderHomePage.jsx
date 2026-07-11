import { Activity, Gauge, Network, Radar, ScanSearch } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { hasAppAccess } from "@/lib/access/appAccess"
import { useAuth } from "@/lib/auth"
import { SpiderBentoAppCards } from "../components/SpiderBentoAppCards"

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

function SpiderHeroIntroSection() {
  return (
    <div className="flex flex-col items-center gap-5 text-center">
      <Badge variant="outline" className="text-sm font-normal">
        Etch Spider
      </Badge>

      <h1 className="text-2xl font-semibold sm:text-3xl lg:text-6xl lg:font-bold">
        <span>AI-Powered </span>
        <span className="shimmer-text">Spec Trend </span>
        <span> Detection</span>
      </h1>

      <p className="text-muted-foreground max-w-4xl text-md">
        Spec 안에 머물러 정상처럼 보이는 미세한 이상 Trend까지 조기에 감지해 품질 사각지대를 줄입니다.
      </p>
    </div>
  )
}

export function SpiderHomePage() {
  const { user } = useAuth()
  const spiderLinkItems = spiderLinks.map((item) => ({
    ...item,
    allowed: hasAppAccess(user, item.appScope),
  }))

  return (
    <div className="relative flex h-full min-h-0 min-w-0 flex-col overflow-hidden">
      <main className="relative z-10 min-h-0 flex-1 overflow-y-auto px-6 py-8">
        <div className="mx-auto grid w-full max-w-7xl gap-6">
          <SpiderHeroIntroSection />

          <SpiderBentoAppCards spiderLinks={spiderLinkItems} />
        </div>
      </main>
    </div>
  )
}
