import { Badge } from "@/components/ui/badge"

import { STATUS_OPTIONS } from "../utils/constants"

export function VocStatusBadge({ status }) {
  const tone = STATUS_OPTIONS.find((option) => option.value === status)?.tone
  return (
    <Badge className={["border", tone].filter(Boolean).join(" ")}>
      {status || "상태 미정"}
    </Badge>
  )
}
