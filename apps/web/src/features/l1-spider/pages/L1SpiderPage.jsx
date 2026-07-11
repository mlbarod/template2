import { useEffect } from "react"

const L1_SPIDER_EXTERNAL_URL = "https://atlas.samsungds.net/d/spider?mode=full"

export function L1SpiderPage() {
  useEffect(() => {
    window.location.replace(L1_SPIDER_EXTERNAL_URL)
  }, [])

  return (
    <div className="flex h-full min-h-0 items-center justify-center bg-background px-6 py-10">
      <div className="w-full max-w-md rounded-2xl border bg-card p-6 text-center">
        <h1 className="text-base font-semibold text-foreground">L1 Spider</h1>
        <p className="mt-2 text-sm text-muted-foreground">외부 Spider 화면으로 이동하고 있습니다.</p>
        <a
          href={L1_SPIDER_EXTERNAL_URL}
          target="_blank"
          rel="noopener noreferrer"
          className="mt-4 inline-flex text-sm font-medium text-primary underline-offset-4 hover:underline"
        >
          새 창에서 열기
        </a>
      </div>
    </div>
  )
}
