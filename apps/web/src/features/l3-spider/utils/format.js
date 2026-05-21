// 파일 경로: src/features/l3-spider/utils/format.js
// L3 Spider 표시 형식 유틸입니다.

export function formatNumber(value) {
  const numeric = Number(value)
  if (!Number.isFinite(numeric)) return "0"
  return new Intl.NumberFormat("ko-KR").format(numeric)
}

export function statusLabel(status) {
  if (status === "High Risk Chamber") return "High Risk"
  if (status === "Warning") return "Warning"
  if (status === "Normal (Ref)") return "Normal"
  return status || "-"
}

export function statusTone(status) {
  if (status === "High Risk Chamber") {
    return "border-destructive/30 bg-destructive/10 text-destructive"
  }
  if (status === "Warning") {
    return "border-chart-4/40 bg-chart-4/10 text-foreground"
  }
  return "border-border bg-muted text-muted-foreground"
}
