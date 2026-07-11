import { cn } from "@/lib/utils"

import "./GaNEtchLogo.css"

const ORBIT_COUNT = 3

function GaNEtchLogoMark({ className, decorative = false, label = "GaN etch logo" }) {
  return (
    <div
      className={cn("react-logo-circles", className)}
      role={decorative ? undefined : "img"}
      aria-label={decorative ? undefined : label}
      aria-hidden={decorative ? "true" : undefined}
    >
      <span />
      {Array.from({ length: ORBIT_COUNT }, (_, index) => (
        <div key={index} />
      ))}
    </div>
  )
}

export function GaNEtchLogo({ className, decorative = false, label = "GaN etch logo", compact = false }) {
  const mark = <GaNEtchLogoMark className={className} decorative={decorative} label={label} />

  if (compact) {
    return mark
  }

  return <div className="react-logo-blank-page">{mark}</div>
}
