import { useEffect, useState } from "react"
import { ChevronLeft, ChevronRight } from "lucide-react"

import { Button } from "@/components/ui/button"
import { normalizeCoverIndex, normalizeScreenshotUrls } from "../utils/appScreenshots"

export function ScreenshotCarousel({ images, altBase = "스크린샷", initialIndex = 0 }) {
  const safeImages = normalizeScreenshotUrls(images)
  const total = safeImages.length
  const [activeIndex, setActiveIndex] = useState(() => normalizeCoverIndex(initialIndex, total))

  useEffect(() => {
    setActiveIndex((prev) => normalizeCoverIndex(prev, total))
  }, [total])

  useEffect(() => {
    setActiveIndex(normalizeCoverIndex(initialIndex, total))
  }, [initialIndex, total])

  if (!total) {
    return (
      <div className="grid w-full aspect-[4/3] place-items-center overflow-hidden rounded-xl border bg-muted">
        <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
          등록된 스크린샷이 없습니다.
        </div>
      </div>
    )
  }

  const handlePrev = () => {
    setActiveIndex((prev) => (total ? (prev - 1 + total) % total : 0))
  }

  const handleNext = () => {
    setActiveIndex((prev) => (total ? (prev + 1) % total : 0))
  }

  return (
    <div className="grid gap-3">
      <div className="relative grid w-full aspect-[4/3] place-items-center overflow-hidden rounded-xl border bg-muted">
        <img
          src={safeImages[activeIndex]}
          alt={`${altBase} ${activeIndex + 1}`}
          className="h-full w-full object-contain"
          loading="lazy"
        />

        {total > 1 ? (
          <>
            <Button
              variant="secondary"
              size="icon"
              type="button"
              className="absolute left-2 top-1/2 -translate-y-1/2 bg-background/70 hover:bg-background"
              onClick={handlePrev}
              aria-label="이전 스크린샷"
            >
              <ChevronLeft className="size-4" />
            </Button>
            <Button
              variant="secondary"
              size="icon"
              type="button"
              className="absolute right-2 top-1/2 -translate-y-1/2 bg-background/70 hover:bg-background"
              onClick={handleNext}
              aria-label="다음 스크린샷"
            >
              <ChevronRight className="size-4" />
            </Button>
            <div className="absolute bottom-2 right-2 rounded bg-background/70 px-2 py-1 text-xs text-muted-foreground">
              {activeIndex + 1} / {total}
            </div>
          </>
        ) : null}
      </div>
    </div>
  )
}
