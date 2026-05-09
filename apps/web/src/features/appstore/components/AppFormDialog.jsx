// 앱스토어 앱 등록/수정 다이얼로그
import { useEffect, useMemo, useState } from "react"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  normalizeCoverIndex,
  normalizeScreenshotUrls,
  resolveAppScreenshots,
} from "../utils/appScreenshots"
import { AppCategorySelect } from "./AppCategorySelect"
import { AppScreenshotInput } from "./AppScreenshotInput"

export function AppFormDialog({
  open,
  onOpenChange,
  onSubmit,
  initialData,
  isSubmitting,
  categoryOptions = [],
  defaultContactName = "",
  defaultContactKnoxid = "",
}) {
  const [name, setName] = useState("")
  const [category, setCategory] = useState("")
  const [url, setUrl] = useState("")
  const [manualUrl, setManualUrl] = useState("")
  const [description, setDescription] = useState("")
  const [contactName, setContactName] = useState("")
  const [contactKnoxid, setContactKnoxid] = useState("")
  const [screenshotUrls, setScreenshotUrls] = useState([])
  const [coverScreenshotIndex, setCoverScreenshotIndex] = useState(0)
  const [screenshotError, setScreenshotError] = useState("")

  useEffect(() => {
    if (!open) return
    if (initialData) {
      setName(initialData.name || "")
      setCategory(initialData.category || "")
      setUrl(initialData.url || "")
      setManualUrl(initialData.manualUrl || "")
      setDescription(initialData.description || "")
      setContactName(initialData.contactName || "")
      setContactKnoxid(initialData.contactKnoxid || "")
      const { urls, coverIndex } = resolveAppScreenshots(initialData)
      setScreenshotUrls(urls)
      setCoverScreenshotIndex(coverIndex)
      setScreenshotError("")
    } else {
      setName("")
      setCategory("")
      setUrl("")
      setManualUrl("")
      setDescription("")
      setContactName("")
      setContactKnoxid("")
      setScreenshotUrls([])
      setCoverScreenshotIndex(0)
      setScreenshotError("")
    }
  }, [initialData, open])

  useEffect(() => {
    if (!open || initialData) return
    setContactName((prev) => (prev ? prev : defaultContactName || ""))
    setContactKnoxid((prev) => (prev ? prev : defaultContactKnoxid || ""))
  }, [defaultContactName, defaultContactKnoxid, initialData, open])

  const title = useMemo(
    () => (initialData ? "앱 정보 수정" : "새 앱 등록"),
    [initialData],
  )
  const normalizedCategoryOptions = useMemo(() => {
    const unique = new Set()
    categoryOptions.forEach((option) => {
      if (typeof option !== "string") return
      const trimmed = option.trim()
      if (trimmed) unique.add(trimmed)
    })
    const currentCategory = initialData?.category
    if (typeof currentCategory === "string" && currentCategory.trim()) {
      unique.add(currentCategory.trim())
    }
    return Array.from(unique)
  }, [categoryOptions, initialData])

  const handleSubmit = async () => {
    if (!name.trim() || !category.trim() || !url.trim()) return
    const normalizedScreenshotUrls = normalizeScreenshotUrls(screenshotUrls)
    const normalizedCoverIndex = normalizeCoverIndex(coverScreenshotIndex, normalizedScreenshotUrls.length)
    const payload = {
      name: name.trim(),
      category: category.trim(),
      url: url.trim(),
      manualUrl: manualUrl.trim(),
      description: description.trim(),
      contactName: contactName.trim(),
      contactKnoxid: contactKnoxid.trim(),
      screenshotUrl: normalizedScreenshotUrls[normalizedCoverIndex] || "",
      screenshotUrls: normalizedScreenshotUrls,
      coverScreenshotIndex: normalizedCoverIndex,
    }
    await onSubmit(payload)
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-xl">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription className="sr-only">앱 정보를 입력하거나 수정합니다.</DialogDescription>
        </DialogHeader>

        <div className="grid gap-4">
          <div className="grid gap-2">
            <Label htmlFor="app-name">앱 이름</Label>
            <Input
              id="app-name"
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="예: Slack Platform"
            />
          </div>

          <div className="grid gap-2">
            <Label htmlFor="app-category-select">카테고리</Label>
            <AppCategorySelect
              category={category}
              categoryOptions={normalizedCategoryOptions}
              onCategoryChange={setCategory}
            />
          </div>

          <div className="grid gap-2">
            <Label htmlFor="app-url">URL</Label>
            <Input
              id="app-url"
              value={url}
              onChange={(event) => setUrl(event.target.value)}
              placeholder="https://example.com"
            />
          </div>

          <div className="grid gap-2">
            <Label htmlFor="app-manual-url">Manual URL</Label>
            <Input
              id="app-manual-url"
              value={manualUrl}
              onChange={(event) => setManualUrl(event.target.value)}
              placeholder="https://example.com/manual"
            />
          </div>

          <div className="grid gap-2">
            <Label htmlFor="app-description">설명</Label>
            <textarea
              id="app-description"
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              placeholder="앱의 주요 기능과 사용 목적을 입력하세요."
              className="min-h-[140px] w-full resize-none rounded-md border bg-background px-3 py-2 text-sm outline-none focus-visible:ring-2 focus-visible:ring-primary/30"
            />
          </div>

          <div className="grid gap-2 sm:grid-cols-2 sm:gap-3">
            <div className="grid gap-2 sm:col-span-2">
              <Label id="app-screenshot-label">스크린샷 (여러 장 붙여넣기)</Label>
              <AppScreenshotInput
                screenshotUrls={screenshotUrls}
                coverScreenshotIndex={coverScreenshotIndex}
                screenshotError={screenshotError}
                onScreenshotUrlsChange={setScreenshotUrls}
                onCoverScreenshotIndexChange={setCoverScreenshotIndex}
                onScreenshotErrorChange={setScreenshotError}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="app-contact-name">담당자 이름</Label>
              <Input
                id="app-contact-name"
                value={contactName}
                onChange={(event) => setContactName(event.target.value)}
                placeholder="홍길동"
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="app-contact-knoxid">담당자 Knox ID</Label>
              <Input
                id="app-contact-knoxid"
                value={contactKnoxid}
                onChange={(event) => setContactKnoxid(event.target.value)}
                placeholder="이메일 @ 앞부분"
              />
            </div>
          </div>
        </div>

        <DialogFooter className="pt-4">
          <Button variant="outline" onClick={() => onOpenChange(false)} type="button">
            취소
          </Button>
          <Button onClick={handleSubmit} disabled={isSubmitting || !name || !category || !url} type="button">
            {initialData ? "수정 완료" : "등록"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
