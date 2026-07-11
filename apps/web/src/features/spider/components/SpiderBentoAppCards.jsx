import { useCallback, useEffect, useId, useLayoutEffect, useRef, useState } from "react"
import { AnimatePresence, motion } from "motion/react"
import {
  ArrowRight,
  Atom,
  ChartNoAxesCombined,
  Database as DatabaseIcon,
  Lock,
  RadioTower,
  ScrollText,
  ServerCog,
  Settings,
} from "lucide-react"
import { Link } from "react-router-dom"

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { MotionPreset } from "@/components/ui/motion-preset"
import spiderLogoDarkPng from "../../../assets/images/spider_darkmode.png"
import spiderLogoLightPng from "../../../assets/images/spider_lightmode.png"

const BENTO_CARD_CLASS = "h-full gap-10 overflow-hidden border border-border/70 bg-background pt-0 shadow-sm dark:bg-card"

function Database(props) {
  return (
    <svg width="30" height="45" viewBox="0 0 66 62" fill="none" xmlns="http://www.w3.org/2000/svg" {...props}>
      <path
        d="M5.15584 16H60.8442M5.15584 16C2.86065 16 1 14.1345 1 11.8333V5.16667C1 2.8655 2.86065 1 5.15584 1H60.8442C63.1393 1 65 2.8655 65 5.16667V11.8333C65 14.1345 63.1393 16 60.8442 16M5.15584 16C2.86065 16 1 17.8655 1 20.1667V26.8333C1 29.1345 2.86065 31 5.15584 31M60.8442 16C63.1393 16 65 17.8655 65 20.1667V26.8333C65 29.1345 63.1393 31 60.8442 31M5.15584 31H60.8442M5.15584 31C2.86065 31 1 32.8655 1 35.1667V41.8333C1 44.1345 2.86065 46 5.15584 46M60.8442 31C63.1393 31 65 32.8655 65 35.1667V41.8333C65 44.1345 63.1393 46 60.8442 46M5.15584 46H60.8442M5.15584 46C2.86065 46 1 47.8655 1 50.1667V56.8333C1 59.1345 2.86065 61 5.15584 61H60.8442C63.1393 61 65 59.1345 65 56.8333V50.1667C65 47.8655 63.1393 46 60.8442 46"
        stroke="currentColor"
        strokeOpacity="0.4"
        strokeWidth="2"
      />
      <path
        d="M8.48047 8.5H23.4415M8.48047 38.5H23.4415M8.48047 53.5H23.4415M8.48047 23.5H23.4415"
        stroke="currentColor"
        strokeOpacity="0.4"
        strokeWidth="2"
        strokeLinecap="round"
      />
      {[8.5, 23.5, 38.5, 53.5].map((cy) => (
        <g key={cy}>
          <path
            d={`M58.3509 ${cy + 2.5}C59.7281 ${cy + 2.5} 60.8444 ${cy + 1.3807} 60.8444 ${cy}C60.8444 ${cy - 1.3807} 59.7281 ${cy - 2.5} 58.3509 ${cy - 2.5}C56.9738 ${cy - 2.5} 55.8574 ${cy - 1.3807} 55.8574 ${cy}C55.8574 ${cy + 1.3807} 56.9738 ${cy + 2.5} 58.3509 ${cy + 2.5}Z`}
            fill="currentColor"
            fillOpacity="0.4"
          />
          <path
            d={`M51.7005 ${cy + 2.5}C53.0777 ${cy + 2.5} 54.194 ${cy + 1.3807} 54.194 ${cy}C54.194 ${cy - 1.3807} 53.0777 ${cy - 2.5} 51.7005 ${cy - 2.5}C50.3234 ${cy - 2.5} 49.207 ${cy - 1.3807} 49.207 ${cy}C49.207 ${cy + 1.3807} 50.3234 ${cy + 2.5} 51.7005 ${cy + 2.5}Z`}
            fill="currentColor"
            fillOpacity="0.4"
          />
        </g>
      ))}
    </svg>
  )
}

function SpiderWebFrame() {
  const spokes = [
    "M384 384 L384 25.6",
    "M384 384 L637.44 130.56",
    "M384 384 L742.4 384",
    "M384 384 L637.44 637.44",
    "M384 384 L384 742.4",
    "M384 384 L130.56 637.44",
    "M384 384 L25.6 384",
    "M384 384 L130.56 130.56",
  ]
  const rings = [
    {
      id: "spider-web-path-inner",
      path: "M384 291.84 L449.28 318.72 L476.16 384 L449.28 449.28 L384 476.16 L318.72 449.28 L291.84 384 L318.72 318.72 Z",
    },
    {
      id: "spider-web-path-mid",
      path: "M384 231.68 L491.52 276.48 L536.32 384 L491.52 491.52 L384 536.32 L276.48 491.52 L231.68 384 L276.48 276.48 Z",
    },
    {
      id: "spider-web-path-outer",
      path: "M384 133.12 L561.92 206.08 L634.88 384 L561.92 561.92 L384 634.88 L206.08 561.92 L133.12 384 L206.08 206.08 Z",
    },
    {
      id: "spider-web-path-edge",
      path: "M384 61.44 L613.12 154.88 L706.56 384 L613.12 613.12 L384 706.56 L154.88 613.12 L61.44 384 L154.88 154.88 Z",
    },
  ]
  const appIcons = [
    {
      pathId: "spider-web-path-edge",
      duration: "30s",
      icons: [
        [DatabaseIcon, "DB", "0s"],
        [ChartNoAxesCombined, "Chart", "-7.5s"],
        [ScrollText, "Log", "-15s"],
        [RadioTower, "Signals", "-22.5s"],
      ],
    },
    {
      pathId: "spider-web-path-outer",
      duration: "22.56s",
      reverse: true,
      icons: [
        [Settings, "Settings", "0s"],
        [ServerCog, "FastAPI", "-5.64s"],
        [Atom, "React", "-11.28s"],
        [DatabaseIcon, "DB", "-16.92s"],
      ],
    },
    {
      pathId: "spider-web-path-mid",
      duration: "17.96s",
      icons: [
        [ChartNoAxesCombined, "Chart", "0s"],
        [RadioTower, "Signals", "-4.49s"],
        [ScrollText, "Log", "-8.98s"],
        [ServerCog, "FastAPI", "-13.47s"],
      ],
    },
    {
      pathId: "spider-web-path-inner",
      duration: "15s",
      reverse: true,
      icons: [
        [Atom, "React", "0s"],
        [Settings, "Settings", "-7.5s"],
      ],
    },
  ]

  return (
    <svg
      className="pointer-events-none absolute inset-0 size-full text-muted-foreground"
      viewBox="0 0 768 768"
      fill="none"
      aria-hidden="true"
    >
      <g stroke="currentColor" strokeWidth="2.25" strokeLinecap="round" strokeLinejoin="round">
        {spokes.map((path) => (
          <path key={path} d={path} opacity="0.45" />
        ))}
        {rings.map((path, index) => (
          <path key={path.id} id={path.id} d={path.path} opacity={0.38 + index * 0.08} />
        ))}
      </g>
      <g
        transform="translate(384 384) scale(0.18) translate(-384 -384)"
        stroke="currentColor"
        strokeWidth="4.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        opacity="0.5"
      >
        {spokes.map((path) => (
          <path key={`center-${path}`} d={path} opacity="0.45" />
        ))}
        {rings.map((path, index) => (
          <path key={`center-${path.id}`} d={path.path} opacity={0.25 + index * 0.12} />
        ))}
      </g>
      {appIcons.flatMap((ring) =>
        ring.icons.map(([Icon, label, begin]) => (
          <g key={`${ring.pathId}-${label}-${begin}`}>
            <foreignObject x="-22" y="-22" width="44" height="44" className="overflow-visible">
              <div
                xmlns="http://www.w3.org/1999/xhtml"
                className="grid size-11 place-content-center rounded-full border border-border/70 bg-background/95 text-primary shadow-sm"
                aria-label={label}
              >
                <Icon className="size-5" aria-hidden="true" />
              </div>
            </foreignObject>
            <animateMotion
              dur={ring.duration}
              begin={begin}
              repeatCount="indefinite"
              calcMode="linear"
              keyPoints={ring.reverse ? "1;0" : undefined}
              keyTimes={ring.reverse ? "0;1" : undefined}
            >
              <mpath href={`#${ring.pathId}`} />
            </animateMotion>
          </g>
        )),
      )}
    </svg>
  )
}

function SpiderCenterLogo() {
  return (
    <span className="absolute left-1/2 top-1/2 z-10 flex size-32 -translate-x-1/2 -translate-y-[47%] items-center justify-center">
      <img src={spiderLogoLightPng} alt="Spider Logo" className="h-22 w-auto object-contain dark:hidden" />
      <img src={spiderLogoDarkPng} alt="Spider Logo" className="hidden h-22 w-auto object-contain dark:block" />
    </span>
  )
}

function OrthogonalBeam({
  className = "",
  containerRef,
  fromRef,
  toRef,
  duration = 4,
  delay = 0,
  pathColor = "currentColor",
  pathWidth = 1,
  pathOpacity = 0.2,
  gradientStartColor = "var(--destructive)",
  gradientStopColor = "currentColor",
}) {
  const id = useId()
  const [pathD, setPathD] = useState("")
  const [svgDimensions, setSvgDimensions] = useState({ width: 0, height: 0 })
  const updatePath = useCallback(() => {
    if (!containerRef.current || !fromRef.current || !toRef.current) {
      return
    }

    const containerRect = containerRef.current.getBoundingClientRect()
    const fromRect = fromRef.current.getBoundingClientRect()
    const toRect = toRef.current.getBoundingClientRect()
    const startX = fromRect.right - containerRect.left
    const startY = fromRect.top - containerRect.top + fromRect.height / 2
    const endX = toRect.left - containerRect.left
    const endY = toRect.top - containerRect.top + toRect.height / 2
    const midX = startX + Math.max(16, (endX - startX) / 2)
    const nextPathD = `M ${startX},${startY} H ${midX} V ${endY} H ${endX}`

    setSvgDimensions((currentDimensions) => {
      if (currentDimensions.width === containerRect.width && currentDimensions.height === containerRect.height) {
        return currentDimensions
      }

      return { width: containerRect.width, height: containerRect.height }
    })
    setPathD((currentPathD) => (currentPathD === nextPathD ? currentPathD : nextPathD))
  }, [containerRef, fromRef, toRef])

  useLayoutEffect(() => {
    updatePath()
  }, [updatePath])

  useEffect(() => {
    const resizeObserver = new ResizeObserver(() => updatePath())

    if (containerRef.current) {
      resizeObserver.observe(containerRef.current)
    }
    if (fromRef.current) {
      resizeObserver.observe(fromRef.current)
    }
    if (toRef.current) {
      resizeObserver.observe(toRef.current)
    }

    updatePath()

    return () => {
      resizeObserver.disconnect()
    }
  }, [containerRef, fromRef, toRef, updatePath])

  return (
    <svg
      fill="none"
      width={svgDimensions.width + 16}
      height={svgDimensions.height + 16}
      xmlns="http://www.w3.org/2000/svg"
      className={`pointer-events-none absolute -left-2 -top-2 transform-gpu overflow-visible stroke-2 ${className}`}
      viewBox={`-8 -8 ${svgDimensions.width + 16} ${svgDimensions.height + 16}`}
    >
      <path d={pathD} stroke={pathColor} strokeWidth={pathWidth} strokeOpacity={pathOpacity} strokeLinecap="round" strokeLinejoin="round" />
      <path d={pathD} stroke={`url(#${id})`} strokeWidth={pathWidth} strokeOpacity="1" strokeLinecap="round" strokeLinejoin="round" />
      <defs>
        <motion.linearGradient
          className="transform-gpu"
          id={id}
          gradientUnits="userSpaceOnUse"
          initial={{
            x1: "0%",
            x2: "0%",
            y1: "0%",
            y2: "0%",
          }}
          animate={{
            x1: ["10%", "110%"],
            x2: ["0%", "100%"],
            y1: ["0%", "0%"],
            y2: ["0%", "0%"],
          }}
          transition={{
            delay,
            duration,
            ease: "linear",
            repeat: Infinity,
            repeatDelay: 0,
          }}
        >
          <stop stopColor={gradientStartColor} stopOpacity="0" />
          <stop stopColor={gradientStartColor} />
          <stop offset="32.5%" stopColor={gradientStopColor} />
          <stop offset="100%" stopColor={gradientStopColor} stopOpacity="0" />
        </motion.linearGradient>
      </defs>
    </svg>
  )
}

function SpiderLinkStack({ links = [], itemRefs = [] }) {
  if (links.length === 0) {
    return null
  }

  return (
    <div className="grid min-w-52 gap-2 sm:min-w-60">
      {links.map((item, index) => {
        const Icon = item.icon
        const className = [
          "group flex min-w-0 items-center gap-2.5 rounded-xl border px-3 py-2 transition-colors sm:gap-3 sm:py-2.5",
          item.allowed
            ? "border-border/70 hover:border-primary/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            : "cursor-not-allowed border-dashed border-border/60 opacity-75",
        ].join(" ")
        const content = (
          <>
            <span className="flex size-9 shrink-0 items-center justify-center rounded-lg border border-border/70 text-muted-foreground sm:size-10">
              <Icon className="size-4.5 sm:size-5" aria-hidden="true" />
            </span>
            <span className="min-w-0 flex-1 truncate text-sm font-medium text-foreground">{item.title}</span>
            {item.allowed ? (
              <span className="inline-flex shrink-0 items-center gap-1 text-primary">
                <motion.span
                  className="shrink-0"
                  animate={{ x: [0, 4, 0, -2, 0] }}
                  transition={{ duration: 1.2, repeat: Infinity, ease: "easeInOut", delay: index * 0.08 }}
                  aria-hidden="true"
                >
                  <ArrowRight className="size-4" />
                </motion.span>
                <span className="shrink-0 text-xs font-medium">앱 바로가기</span>
              </span>
            ) : (
              <Lock className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
            )}
          </>
        )

        return item.allowed ? (
          <Link
            key={item.title}
            ref={itemRefs[index]}
            to={item.href}
            target={item.external ? "_blank" : undefined}
            rel={item.external ? "noopener noreferrer" : undefined}
            className={className}
          >
            {content}
          </Link>
        ) : (
          <div key={item.title} ref={itemRefs[index]} className={className} aria-disabled="true">
            {content}
          </div>
        )
      })}
    </div>
  )
}

function ThemeSharing({ spiderLinks = [] }) {
  const containerRef = useRef(null)
  const span1Ref = useRef(null)
  const link1Ref = useRef(null)
  const link2Ref = useRef(null)
  const link3Ref = useRef(null)
  const link4Ref = useRef(null)
  const link5Ref = useRef(null)
  const linkRefs = [link1Ref, link2Ref, link3Ref, link4Ref, link5Ref]

  return (
    <div ref={containerRef} className="relative z-1 flex w-full max-w-2xl items-center justify-center gap-6 px-4 sm:px-6">
      <div className="flex min-w-0 items-center gap-12 sm:gap-20">
        <span className="relative flex shrink-0 items-center justify-center">
          <span ref={span1Ref} className="relative flex overflow-hidden rounded-md">
            <Database className="relative z-10 h-20 w-auto sm:h-24" />
            <MotionPreset
              className="absolute inset-x-0 -bottom-1/3 z-20 h-1/3 border-t border-primary/70 bg-linear-to-b from-primary/30 via-primary/10 to-transparent"
              motionProps={{
                animate: {
                  bottom: ["-33%", "100%", "-33%"],
                  rotateX: ["0deg", "0deg", "180deg", "180deg", "0deg"],
                },
                transition: {
                  duration: 3.5,
                  delay: 0.8,
                  repeat: Infinity,
                  ease: "linear",
                  times: [0, 0.499, 0.5, 0.999, 1],
                },
              }}
            />
          </span>
          <span className="absolute top-full mt-2 text-sm">Database</span>
        </span>
        <SpiderLinkStack links={spiderLinks} itemRefs={linkRefs} />
      </div>

      {spiderLinks.slice(0, linkRefs.length).map((item, index) => (
        <OrthogonalBeam
          key={item.title}
          containerRef={containerRef}
          fromRef={span1Ref}
          toRef={linkRefs[index]}
          className="text-primary -z-1"
          duration={4}
          delay={index * 0.18}
        />
      ))}
    </div>
  )
}

function ThemeSharingCard({ spiderLinks = [] }) {
  return (
    <MotionPreset fade blur slide={{ direction: "down", offset: 75 }} transition={{ duration: 0.45 }} className="h-full md:col-span-2">
      <Card className={BENTO_CARD_CLASS}>
        <CardContent className="flex h-88 items-start justify-center overflow-visible pt-3">
          <ThemeSharing spiderLinks={spiderLinks} />
        </CardContent>
        <CardHeader className="gap-4">
          <CardTitle className="text-center text-2xl font-semibold text-primary">복합 데이터 기반 사전 감지</CardTitle>
          <CardDescription className="text-center text-lg">
            설비, 공정, 계측, 이력 데이터를 복합적으로 수집해 단일 지표만으로는 보이지 않는 이상 패턴을 함께 판단합니다.
            누적 흐름과 상관 신호를 기반으로 불량 가능성을 사전에 감지해 더 정확한 선제 대응을 지원합니다.
          </CardDescription>
        </CardHeader>
      </Card>
    </MotionPreset>
  )
}

function SeamlessIntegrationsCard() {
  return (
    <MotionPreset fade blur slide={{ direction: "down", offset: 75 }} transition={{ duration: 0.45 }} className="h-full overflow-hidden">
      <Card className={BENTO_CARD_CLASS}>
        <MotionPreset
          fade
          slide={{ direction: "down", offset: 50 }}
          delay={0.1}
          transition={{ duration: 0.45 }}
          className="relative flex h-88 justify-center overflow-hidden [-webkit-mask-image:radial-gradient(ellipse_at_center,black_68%,transparent_88%)] [mask-image:radial-gradient(ellipse_at_center,black_58%,transparent_82%)]"
        >
          <div className="absolute left-1/2 top-1/2 size-[40rem] -translate-x-1/2 -translate-y-1/2">
            <SpiderWebFrame />
            <SpiderCenterLogo />
          </div>
        </MotionPreset>
        <CardHeader className="gap-4">
          <MotionPreset fade slide={{ direction: "down", offset: 50 }} delay={0.25} transition={{ duration: 0.45 }}>
            <CardTitle className="text-center text-2xl font-semibold text-primary">놓침 없는 커버리지</CardTitle>
          </MotionPreset>
          <MotionPreset fade slide={{ direction: "down", offset: 50 }} delay={0.4} transition={{ duration: 0.45 }}>
            <CardDescription className="text-center text-lg">
              엔지니어가 직접 보기 어려운 사각지대와 놓치기 쉬운 이상 흐름까지 SPIDER가 빠짐없이 커버합니다.
            </CardDescription>
          </MotionPreset>
        </CardHeader>
      </Card>
    </MotionPreset>
  )
}

function BoostEfficiencyCover({ children }) {
  const [hovered, setHovered] = useState(false)
  const beamPositions = [
    "top-[8%]",
    "top-[16%]",
    "top-[24%]",
    "top-[32%]",
    "top-[40%]",
    "top-[48%]",
    "top-[56%]",
    "top-[64%]",
    "top-[72%]",
    "top-[80%]",
    "top-[88%]",
  ]
  const sparklePositions = [
    "left-[7%] top-[16%] size-0.75",
    "left-[12%] top-[50%] size-1.5",
    "left-[18%] top-[78%] size-0.5",
    "left-[24%] top-[30%] size-1",
    "left-[32%] top-[88%] size-0.75",
    "left-[40%] top-[12%] size-1.5",
    "left-[48%] top-[60%] size-0.5",
    "right-[7%] top-[28%] size-1.5",
    "right-[14%] bottom-[14%] size-0.75",
    "right-[22%] top-[8%] size-0.5",
    "right-[30%] bottom-[30%] size-1.5",
    "right-[40%] top-[82%] size-0.75",
    "right-[50%] top-[22%] size-0.5",
    "right-[56%] bottom-[8%] size-1",
  ]

  return (
    <div
      className="group/cover relative flex h-56 w-full items-center justify-center overflow-hidden rounded-sm px-2 py-2 transition duration-200"
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      <AnimatePresence>
        {hovered ? (
          <motion.div
            className="absolute inset-0"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.18 }}
          >
            <motion.div
              className="absolute inset-0 flex w-[220%]"
              animate={{ x: ["-54%", "0%"] }}
              transition={{ duration: 5.4, repeat: Infinity, ease: "linear" }}
            >
              {[0, 1].map((layer) => (
                <div key={layer} className="relative h-full w-full">
                  {sparklePositions.map((position, index) => (
                    <motion.span
                      key={`${layer}-${position}`}
                      className={`absolute rounded-full bg-primary ${position}`}
                      animate={{ opacity: [0, 1, 0], scale: [0.25, 1.9, 0.25], y: [14, -18, 14] }}
                      transition={{ duration: 0.72, delay: index * 0.055, repeat: Infinity, ease: "easeInOut" }}
                      aria-hidden="true"
                    />
                  ))}
                </div>
              ))}
            </motion.div>
          </motion.div>
        ) : null}
      </AnimatePresence>
      <motion.div
        className="absolute inset-0"
        animate={{ opacity: hovered ? [0.5, 1, 0.5] : [0.16, 0.34, 0.16], x: ["-12%", "12%", "-12%"], scale: hovered ? [0.9, 1.18, 0.9] : [0.95, 1.05, 0.95] }}
        transition={{ duration: hovered ? 0.95 : 3.6, repeat: Infinity, ease: "easeInOut" }}
      >
        <div className="absolute inset-y-0 left-1/2 w-4/5 -translate-x-1/2 bg-[radial-gradient(circle,var(--primary)_0,transparent_62%)] opacity-25 blur-2xl" />
      </motion.div>
      <motion.span
        className="absolute bottom-[12%] left-1/2 h-24 w-10 -translate-x-1/2 rounded-full bg-linear-to-b from-primary/40 via-primary/15 to-transparent blur-md"
        animate={{ opacity: hovered ? [0.2, 0.9, 0.2] : [0.1, 0.35, 0.1], scaleY: hovered ? [0.7, 1.35, 0.7] : [0.8, 1.05, 0.8] }}
        transition={{ duration: hovered ? 0.32 : 1.5, repeat: Infinity, ease: "easeInOut" }}
        aria-hidden="true"
      />
      {beamPositions.map((position, index) => (
        <motion.span
          key={position}
          className={`absolute z-0 h-px ${index % 2 === 0 ? "w-32" : "w-24"} rounded-full bg-linear-to-r from-transparent via-primary/75 to-transparent ${position}`}
          initial={{ x: "-150%", opacity: 0 }}
          animate={{ x: hovered ? "170%" : "145%", opacity: hovered ? [0.12, 0.82, 0.12] : [0.06, index % 2 === 0 ? 0.56 : 0.42, 0.06] }}
          transition={{ duration: hovered ? 0.42 : 1.35, delay: index * 0.05, repeat: Infinity, repeatDelay: hovered ? 0.08 : 0.35, ease: "linear" }}
          aria-hidden="true"
        />
      ))}
      <motion.span
        key={String(hovered)}
        className="relative z-10 inline-flex transition duration-200 group-hover/cover:text-primary"
        animate={{
          scale: hovered ? 0.76 : [1, 1.06, 1],
          x: hovered ? [0, -42, 42, -34, 34, 0] : [0, 4, 0],
          y: hovered ? [0, 62, -62, 50, -50, 0] : [0, -16, 0],
          rotate: hovered ? [0, -14, 14, -12, 12, 0] : [-4, 4, -4],
        }}
        transition={{
          duration: hovered ? 0.16 : 1.9,
          repeat: Infinity,
          ease: hovered ? "linear" : "easeInOut",
          scale: { duration: 0.16, repeat: hovered ? 0 : Infinity },
        }}
      >
        {children}
      </motion.span>
    </div>
  )
}

function BoostEfficiencyCard() {
  return (
    <MotionPreset fade blur slide={{ direction: "down", offset: 75 }} transition={{ duration: 0.45 }} className="h-full overflow-hidden xl:col-start-4">
      <Card className={BENTO_CARD_CLASS}>
        <MotionPreset
          fade
          slide={{ direction: "down", offset: 50 }}
          delay={0.1}
          transition={{ duration: 0.45 }}
          className="flex h-88 items-center justify-center overflow-visible"
        >
          <BoostEfficiencyCover>
            <img src="https://cdn.shadcnstudio.com/ss-assets/blocks/bento-grid/image-97.png" alt="rocket" className="h-19.25" />
          </BoostEfficiencyCover>
        </MotionPreset>
        <CardHeader className="gap-4">
          <MotionPreset fade slide={{ direction: "down", offset: 50 }} delay={0.25} transition={{ duration: 0.45 }}>
            <CardTitle className="text-center text-2xl font-semibold text-primary">생산성 극대화</CardTitle>
          </MotionPreset>
          <MotionPreset fade slide={{ direction: "down", offset: 50 }} delay={0.4} transition={{ duration: 0.45 }}>
            <CardDescription className="text-center text-lg">
              반복 확인과 수작업 판단 부담을 줄이고, 필요한 대응에 집중할 수 있게 해 업무 효율과 생산성을 높입니다.
            </CardDescription>
          </MotionPreset>
        </CardHeader>
      </Card>
    </MotionPreset>
  )
}

export function SpiderBentoAppCards({ spiderLinks = [] }) {
  return (
    <section
      aria-label="Imported app cards"
      className="mx-auto grid w-full max-w-7xl grid-cols-1 gap-4 rounded-3xl border border-border bg-muted/70 p-4 shadow-sm md:grid-cols-2 xl:grid-cols-4"
    >
      <SeamlessIntegrationsCard />
      <ThemeSharingCard spiderLinks={spiderLinks} />
      <BoostEfficiencyCard />
    </section>
  )
}
