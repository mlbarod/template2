import { PlusCircle } from "lucide-react"

import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import {
  APP_CATEGORIES,
  RICH_TEXT_EDITOR_FORMATS,
  RICH_TEXT_EDITOR_MODULES,
} from "../utils/constants"
import { RichTextEditor } from "./RichTextEditor"

export function VocCreateDialog({
  open,
  onOpenChange,
  form,
  updateForm,
  resetForm,
  onSubmit,
  isSubmitting,
  isSubmitDisabled,
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogTrigger asChild>
        <Button className="self-start sm:ml-auto">
          <PlusCircle className="size-4" aria-hidden="true" />
          새 글 작성
        </Button>
      </DialogTrigger>
      <DialogContent className="w-[min(1100px,calc(100%-2rem))] min-w-[min(1100px,calc(100%-2rem))] max-w-[min(1100px,calc(100%-2rem))] h-[80vh] min-h-[80vh] max-h-[80vh] overflow-y-auto overflow-x-hidden">
        <DialogHeader>
          <DialogTitle>새 글 작성</DialogTitle>
          <DialogDescription className="sr-only">
            VOC 게시판 새 글을 작성합니다.
          </DialogDescription>
        </DialogHeader>
        <form className="space-y-4" onSubmit={onSubmit}>
          <div className="space-y-2">
            <label className="text-sm font-medium text-foreground" htmlFor="voc-app">
              앱 카테고리
            </label>
            <select
              id="voc-app"
              value={form.app}
              onChange={(event) => updateForm("app", event.target.value)}
              className="h-10 w-full rounded-md border border-input bg-background px-3 text-sm text-foreground shadow-sm focus:outline-none focus:ring-2 focus:ring-ring/50"
              required
            >
              {APP_CATEGORIES.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium text-foreground" htmlFor="voc-title">
              제목
            </label>
            <Input
              id="voc-title"
              value={form.title}
              onChange={(event) => updateForm("title", event.target.value)}
              placeholder="무엇을 도와드릴까요?"
              required
            />
          </div>
          <div className="space-y-2">
            <label
              className="text-sm font-medium text-foreground"
              id="voc-content-label"
              htmlFor="voc-content-editor"
            >
              내용
            </label>
            <RichTextEditor
              id="voc-content-editor"
              value={form.content}
              onChange={(value) => updateForm("content", value)}
              modules={RICH_TEXT_EDITOR_MODULES}
              formats={RICH_TEXT_EDITOR_FORMATS}
              placeholder="상세한 내용을 적어 주세요."
              ariaLabelledby="voc-content-label"
            />
          </div>

          <DialogFooter>
            <Button type="button" variant="ghost" onClick={resetForm} disabled={isSubmitting}>
              초기화
            </Button>
            <Button type="submit" disabled={isSubmitDisabled}>
              <PlusCircle className="size-4" aria-hidden="true" />
              {isSubmitting ? "등록 중..." : "등록"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
