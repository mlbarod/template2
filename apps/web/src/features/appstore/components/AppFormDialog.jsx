// 앱스토어 앱 등록/수정 다이얼로그
import { useEffect, useMemo, useState } from "react"
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { cn } from "@/lib/utils"

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

const CATEGORY_OPTIONS = [
  "DX App",
  "Engineer App",
  "Etch Report",
  "PM Report",
  "품질 Report",
  "환경안전 Report",
  "생산지원 Report",
  "설치기술 Report",
]

export function AppFormDialog({
  open,
  onOpenChange,
  onSubmit,
  initialData,
  isSubmitting,
  defaultContactName = "",
  defaultContactKnoxid = "",
}) {
  const [name, setName] = useState("")
  const [category, setCategory] = useState("")
  const [url, setUrl] = useState("")
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
      setDescription(initialData.description || "")
      setContactName(initialData.contactName || "")
      setContactKnoxid(initialData.contactKnoxid || "")
      const urls = Array.isArray(initialData.screenshotUrls)
        ? initialData.screenshotUrls.filter((value) => typeof value === "string" && value.trim())
        : []
      const resolvedUrls =
        urls.length > 0
          ? urls
          : typeof initialData.screenshotUrl === "string" && initialData.screenshotUrl.trim()
            ? [initialData.screenshotUrl.trim()]
            : []
      const coverIndexRaw = initialData.coverScreenshotIndex ?? 0
      const coverIndex = Number.isFinite(Number(coverIndexRaw)) ? Number(coverIndexRaw) : 0
      setScreenshotUrls(resolvedUrls)
      setCoverScreenshotIndex(
        Number.isInteger(coverIndex) && coverIndex >= 0 && coverIndex < resolvedUrls.length ? coverIndex : 0,
      )
      setScreenshotError("")
    } else {
      setName("")
      setCategory("")
      setUrl("")
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

  const handleSubmit = async () => {
    if (!name.trim() || !category.trim() || !url.trim()) return
    const normalizedScreenshotUrls = screenshotUrls
      .filter((value) => typeof value === "string")
      .map((value) => value.trim())
      .filter(Boolean)
    const normalizedCoverIndex =
      Number.isInteger(coverScreenshotIndex) &&
      coverScreenshotIndex >= 0 &&
      coverScreenshotIndex < normalizedScreenshotUrls.length
        ? coverScreenshotIndex
        : 0
    const payload = {
      name: name.trim(),
      category: category.trim(),
      url: url.trim(),
      description: description.trim(),
      contactName: contactName.trim(),
      contactKnoxid: contactKnoxid.trim(),
      screenshotUrl: normalizedScreenshotUrls[normalizedCoverIndex] || "",
      screenshotUrls: normalizedScreenshotUrls,
      coverScreenshotIndex: normalizedCoverIndex,
    }
    await onSubmit(payload)
  }

  const handleScreenshotPaste = async (event) => {
    const files = getClipboardImageFiles(event.clipboardData)
    if (!files.length) {
      setScreenshotError("이미지(스크린샷)만 붙여넣을 수 있어요.")
      return
    }

    event.preventDefault()
    setScreenshotError("")

    try {
      const dataUrls = await Promise.all(files.map((file) => fileToDataUrl(file)))
      const nextUrls = dataUrls.filter(Boolean)
      setScreenshotUrls((prev) => [...prev, ...nextUrls])
    } catch {
      setScreenshotError("스크린샷을 읽지 못했습니다. 다시 시도해 주세요.")
    }
  }

  const coverSrc = screenshotUrls[coverScreenshotIndex] || ""

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-xl">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
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
            <Label htmlFor="app-category">카테고리</Label>
            <Select value={category} onValueChange={setCategory}>
              <SelectTrigger id="app-category">
                <SelectValue placeholder="카테고리 선택" />
              </SelectTrigger>
              <SelectContent>
                {CATEGORY_OPTIONS.map((option) => (
                  <SelectItem key={option} value={option}>
                    {option}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
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
                            onClick={() => setCoverScreenshotIndex(index)}
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
                            onClick={() => {
                              setScreenshotUrls((prev) => prev.filter((_, i) => i !== index))
                              setCoverScreenshotIndex((prevIndex) => {
                                if (index === prevIndex) return 0
                                if (index < prevIndex) return Math.max(prevIndex - 1, 0)
                                return prevIndex
                              })
                            }}
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
                      onClick={() => {
                        setScreenshotUrls([])
                        setCoverScreenshotIndex(0)
                        setScreenshotError("")
                      }}
                      type="button"
                    >
                      전체 삭제
                    </Button>
                  ) : null}
                </div>
              </div>
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
