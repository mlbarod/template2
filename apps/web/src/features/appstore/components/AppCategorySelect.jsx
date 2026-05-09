import { useEffect, useMemo, useRef, useState } from "react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectSeparator,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"

const MAX_CATEGORY_LENGTH = 100

export function AppCategorySelect({ category, categoryOptions, onCategoryChange }) {
  const [isOpen, setIsOpen] = useState(false)
  const [isAddingCategory, setIsAddingCategory] = useState(false)
  const [newCategoryName, setNewCategoryName] = useState("")
  const newCategoryInputRef = useRef(null)

  useEffect(() => {
    if (!isAddingCategory || !isOpen) return undefined
    const frameId = requestAnimationFrame(() => {
      newCategoryInputRef.current?.focus()
    })
    return () => cancelAnimationFrame(frameId)
  }, [isAddingCategory, isOpen])

  const categorySelectOptions = useMemo(() => {
    const unique = new Set()
    categoryOptions.forEach((option) => {
      if (typeof option !== "string") return
      const trimmed = option.trim()
      if (trimmed) unique.add(trimmed)
    })
    const trimmedCategory = category.trim()
    if (trimmedCategory) unique.add(trimmedCategory)
    return Array.from(unique)
  }, [category, categoryOptions])

  const selectedCategoryOption = categorySelectOptions.includes(category.trim()) ? category.trim() : ""

  const closeCategoryInput = () => {
    setIsAddingCategory(false)
    setNewCategoryName("")
  }

  const handleOpenChange = (nextOpen) => {
    setIsOpen(nextOpen)
    if (!nextOpen) closeCategoryInput()
  }

  const handleCategorySelect = (value) => {
    onCategoryChange(value)
    closeCategoryInput()
    setIsOpen(false)
  }

  const handleAddCategory = () => {
    const nextCategory = newCategoryName.trim()
    if (!nextCategory) return
    onCategoryChange(nextCategory)
    closeCategoryInput()
    setIsOpen(false)
  }

  const openCategoryInput = (event) => {
    event.preventDefault()
    event.stopPropagation()
    setIsAddingCategory(true)
    setNewCategoryName("")
    setIsOpen(true)
  }

  return (
    <Select
      open={isOpen}
      onOpenChange={handleOpenChange}
      value={selectedCategoryOption}
      onValueChange={handleCategorySelect}
    >
      <SelectTrigger id="app-category-select" aria-label="기존 카테고리 선택" className="w-full">
        <SelectValue placeholder={categorySelectOptions.length ? "기존 카테고리 선택" : "기존 카테고리 없음"} />
      </SelectTrigger>
      <SelectContent>
        {categorySelectOptions.map((option) => (
          <SelectItem key={option} value={option}>
            {option}
          </SelectItem>
        ))}
        {categorySelectOptions.length > 0 ? <SelectSeparator /> : null}
        {isAddingCategory ? (
          <div
            className="grid gap-2 p-2"
            onPointerDownCapture={(event) => event.stopPropagation()}
          >
            <div className="flex items-center gap-2">
              <Input
                id="app-category-new"
                ref={newCategoryInputRef}
                value={newCategoryName}
                onChange={(event) => setNewCategoryName(event.target.value)}
                onKeyDown={(event) => {
                  event.stopPropagation()
                  if (event.key === "Enter") {
                    event.preventDefault()
                    handleAddCategory()
                  }
                  if (event.key === "Escape") {
                    event.preventDefault()
                    closeCategoryInput()
                  }
                }}
                placeholder="새 카테고리 입력"
                maxLength={MAX_CATEGORY_LENGTH}
                className="h-8"
                autoFocus
              />
              <Button
                type="button"
                size="sm"
                variant="secondary"
                onClick={handleAddCategory}
                disabled={!newCategoryName.trim()}
                className="h-8 shrink-0"
              >
                추가
              </Button>
            </div>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={closeCategoryInput}
              className="h-7 justify-start px-2 text-xs text-muted-foreground"
            >
              취소
            </Button>
          </div>
        ) : (
          <button
            type="button"
            className="relative flex w-full cursor-pointer items-center rounded-sm px-2 py-1.5 text-sm text-muted-foreground outline-none hover:bg-accent hover:text-accent-foreground focus:bg-accent focus:text-accent-foreground"
            onPointerDown={openCategoryInput}
            onKeyDown={(event) => {
              if (event.key !== "Enter" && event.key !== " ") return
              openCategoryInput(event)
            }}
          >
            + 새 카테고리 추가
          </button>
        )}
      </SelectContent>
    </Select>
  )
}
