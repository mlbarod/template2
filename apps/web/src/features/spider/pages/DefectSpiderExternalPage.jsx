import { useEffect } from "react"

function readEnvValue(key) {
  if (typeof import.meta !== "undefined" && import.meta.env && key in import.meta.env) {
    const value = import.meta.env[key]
    if (typeof value === "string" && value.trim()) return value.trim()
  }
  return ""
}

const DEFECT_SPIDER_EXTERNAL_URL = readEnvValue("VITE_DEFECT_SPIDER_URL")

export function DefectSpiderExternalPage() {
  useEffect(() => {
    if (!DEFECT_SPIDER_EXTERNAL_URL) return
    window.location.replace(DEFECT_SPIDER_EXTERNAL_URL)
  }, [])

  return (
    <div className="flex h-full min-h-0 items-center justify-center bg-background px-6 py-10">
      <div className="w-full max-w-md rounded-2xl border bg-card p-6 text-center">
        <h1 className="text-base font-semibold text-foreground">Defect Spider</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          {DEFECT_SPIDER_EXTERNAL_URL
            ? "외부 Defect Spider 화면으로 이동하고 있습니다."
            : "Defect Spider 외부 링크가 설정되지 않았습니다."}
        </p>
        {DEFECT_SPIDER_EXTERNAL_URL ? (
          <a
            href={DEFECT_SPIDER_EXTERNAL_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="mt-4 inline-flex text-sm font-medium text-primary underline-offset-4 hover:underline"
          >
            새 창에서 열기
          </a>
        ) : null}
      </div>
    </div>
  )
}
