const TTTM_SPIDER_URL = "http://10.172.60.187:32710"

export function TttmSpiderPage() {
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
