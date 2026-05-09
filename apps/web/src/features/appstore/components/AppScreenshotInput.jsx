import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import { getCoverScreenshotUrl } from "../utils/appScreenshots"

function getClipboardImageFiles(clipboardData) {
  const items = Array.from(clipboardData?.items ?? [])
  return items
    .filter((item) => item.kind === "file" && item.type?.startsWith("image/"))
    .map((item) => item.getAsFile())
    .filter(Boolean)
}

function fileToDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(typeof reader.result === "string" ? reader.result : "")
    reader.onerror = () => reject(reader.error || new Error("Failed to read file"))
    reader.readAsDataURL(file)
  })
}

export function AppScreenshotInput({
  screenshotUrls,
  coverScreenshotIndex,
  screenshotError,
  onScreenshotUrlsChange,
  onCoverScreenshotIndexChange,
  onScreenshotErrorChange,
}) {
  const coverSrc = getCoverScreenshotUrl({ screenshotUrls, coverScreenshotIndex })

  const handleScreenshotPaste = async (event) => {
    const files = getClipboardImageFiles(event.clipboardData)
    if (!files.length) {
      onScreenshotErrorChange("이미지(스크린샷)만 붙여넣을 수 있어요.")
      return
    }

    event.preventDefault()
    onScreenshotErrorChange("")

    try {
      const dataUrls = await Promise.all(files.map((file) => fileToDataUrl(file)))
      const nextUrls = dataUrls.filter(Boolean)
      onScreenshotUrlsChange((prev) => [...prev, ...nextUrls])
    } catch {
      onScreenshotErrorChange("스크린샷을 읽지 못했습니다. 다시 시도해 주세요.")
    }
  }

  const handleRemoveScreenshot = (index) => {
    onScreenshotUrlsChange((prev) => prev.filter((_, currentIndex) => currentIndex !== index))
    onCoverScreenshotIndexChange((prevIndex) => {
      if (index === prevIndex) return 0
      if (index < prevIndex) return Math.max(prevIndex - 1, 0)
      return prevIndex
    })
  }

  const handleClearScreenshots = () => {
    onScreenshotUrlsChange([])
    onCoverScreenshotIndexChange(0)
    onScreenshotErrorChange("")
  }

  return (
    <div className="grid gap-2">
      <div
        id="app-screenshot"
        aria-labelledby="app-screenshot-label"
        tabIndex={0}
        onPaste={handleScreenshotPaste}
        className="grid min-h-[140px] place-items-center rounded-md border bg-muted/40 p-3 text-sm outline-none focus-visible:ring-2 focus-visible:ring-primary/30"
      >
        {coverSrc ? (
          <img
            src={coverSrc}
            alt="대표 스크린샷 미리보기"
            className="max-h-56 w-full rounded-md object-cover"
            loading="lazy"
          />
        ) : (
          <div className="grid gap-2 text-center">
            <p className="text-sm font-medium text-foreground">여기에 스크린샷을 붙여넣어 주세요</p>
            <p className="text-xs text-muted-foreground">Ctrl+V / ⌘V</p>
          </div>
        )}
      </div>

      {screenshotError ? (
        <p className="text-xs text-destructive">{screenshotError}</p>
      ) : null}

      {screenshotUrls.length ? (
        <div className="grid grid-cols-3 gap-2">
          {screenshotUrls.map((src, index) => {
            const isCover = index === coverScreenshotIndex
            return (
              <div key={`${index}-${src.slice(0, 24)}`} className="grid gap-1">
                <button
                  type="button"
                  onClick={() => onCoverScreenshotIndexChange(index)}
                  className={cn(
                    "relative overflow-hidden rounded-md border bg-muted/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/30",
                    isCover && "ring-2 ring-primary/40",
                  )}
                >
                  <img
                    src={src}
                    alt={`스크린샷 ${index + 1}`}
                    className="h-20 w-full object-cover"
                    loading="lazy"
                  />
                  {isCover ? (
                    <div className="absolute left-1 top-1 rounded bg-primary px-1.5 py-0.5 text-[10px] font-medium text-primary-foreground">
                      대표
                    </div>
                  ) : null}
                </button>
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-7 px-2 text-xs"
                  onClick={() => handleRemoveScreenshot(index)}
                  type="button"
                >
                  삭제
                </Button>
              </div>
            )
          })}
        </div>
      ) : null}

      <div className="flex items-center justify-between gap-2">
        <p className="text-xs text-muted-foreground">
          {screenshotUrls.length
            ? `${screenshotUrls.length}장 등록됨 · 대표 이미지를 선택하세요.`
            : "클릭 후 붙여넣기(Ctrl+V)를 사용하세요."}
        </p>
        {screenshotUrls.length ? (
          <Button
            variant="ghost"
            size="sm"
            onClick={handleClearScreenshots}
            type="button"
          >
            전체 삭제
          </Button>
        ) : null}
      </div>
    </div>
  )
}
