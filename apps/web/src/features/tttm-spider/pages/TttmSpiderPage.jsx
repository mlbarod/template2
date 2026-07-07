function readEnvValue(key) {
  if (typeof import.meta !== "undefined" && import.meta.env && key in import.meta.env) {
    const value = import.meta.env[key]
    if (typeof value === "string" && value.trim()) return value.trim()
  }
  if (typeof process !== "undefined" && process.env && key in process.env) {
    const value = process.env[key]
    if (typeof value === "string" && value.trim()) return value.trim()
  }
  return ""
}

const TTTM_SPIDER_URL = readEnvValue("VITE_TTTM_SPIDER_URL")

export function TttmSpiderPage() {
  if (!TTTM_SPIDER_URL) {
    return (
      <div className="flex h-full min-h-0 items-center justify-center p-6">
        <div className="rounded-lg border border-dashed bg-card px-6 py-5 text-center text-sm text-muted-foreground">
          <p className="font-medium text-foreground">TTTM Spider URL이 설정되지 않았습니다.</p>
          <p className="mt-1">VITE_TTTM_SPIDER_URL 환경 변수를 설정해 주세요.</p>
        </div>
      </div>
    )
  }

  return (
    <div className="flex h-full min-h-0 min-w-0 flex-col bg-background">
      <iframe
        title="TTTM Spider"
        src={TTTM_SPIDER_URL}
        className="h-full min-h-0 w-full flex-1 border-0 bg-background"
        loading="eager"
        referrerPolicy="no-referrer-when-downgrade"
        allow="fullscreen; clipboard-read; clipboard-write"
      />
    </div>
  )
}
