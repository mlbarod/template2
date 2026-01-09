// 앱스토어 필터 패널
import { Plus, Search, X } from "lucide-react"

import { CATEGORY_OPTIONS } from "./AppFormDialog"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"

const ALL_CATEGORY = "all"
const CATEGORY_ORDER_SET = new Set(CATEGORY_OPTIONS)

const getCategoryLabel = (option) => (option === ALL_CATEGORY ? "Total" : option)
const getOrderedCategories = (categories) => {
  const categorySet = new Set(categories)

  return [
    ...(categorySet.has(ALL_CATEGORY) ? [ALL_CATEGORY] : []),
    ...CATEGORY_OPTIONS.filter((option) => categorySet.has(option)),
    ...categories.filter(
      (option) => option !== ALL_CATEGORY && !CATEGORY_ORDER_SET.has(option),
    ),
  ]
}

export function AppFilters({
  totalApps,
  query,
  onQueryChange,
  category,
  categories,
  categoryCounts,
  onCategoryChange,
  onReset,
  onCreate,
  isCreating,
}) {
  const categoryCount = (option) =>
    option === ALL_CATEGORY ? totalApps : categoryCounts?.[option] ?? 0
  const orderedCategories = getOrderedCategories(categories)
  const totalCategoryCount = Math.max(categories.length - 1, 0)
  const hasQuery = Boolean(query)

  return (
    <div className="grid h-full min-h-0 grid-rows-[auto_1fr] gap-2">
      {/* 상단: 요약 + 주요 액션 */}
      <Card className="rounded-2xl border bg-card shadow-sm">
        <CardHeader className="space-y-3 pb-3">
          <div className="flex justify-between">
            <CardTitle className="text-xl">App store </CardTitle>
            <Button
              variant="default"
              size="sm"
              onClick={onCreate}
              disabled={isCreating}
              className="gap-1"
              type="button"
            >
              <Plus className="size-4" />
              Add
            </Button>
          </div>
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <span className="inline-flex items-center rounded-full bg-muted px-2.5 py-1 text-xs text-muted-foreground">
                {totalCategoryCount} Categories
              </span>
              <span className="inline-flex items-center rounded-full bg-muted px-2.5 py-1 text-xs text-muted-foreground">
                {totalApps} apps
              </span>
            </div>
          </div>
          <CardDescription className="text-sm pt-4">
            Etch 기술팀에서 사용하는 앱을 빠르게 찾고 관리합니다.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex min-h-0 flex-1 flex-col gap-3">
          <div className="relative">
            <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={query}
              onChange={(event) => onQueryChange(event.target.value)}
              placeholder="앱 이름, 설명, 카테고리 검색"
              className="h-10 pl-9 pr-9"
            />
            {hasQuery ? (
              <Button
                variant="ghost"
                size="icon"
                onClick={() => onQueryChange("")}
                type="button"
                className="absolute right-1 top-1/2 size-8 -translate-y-1/2 text-muted-foreground"
                aria-label="검색어 지우기"
              >
                <X className="size-4" />
              </Button>
            ) : null}
          </div>
        </CardContent>
      </Card>

      {/* 하단: 검색 + 필터 */}
      <Card className="min-h-0 rounded-2xl border bg-card shadow-sm">
        <CardContent className="flex min-h-0 flex-1 flex-col gap-3">
          {/* 검색 */}
          {/* 카테고리 목록 */}
          <div className="flex items-center justify-between">
            <div className="text-sm font-medium">Category</div>
            <Button
              variant="ghost"
              size="sm"
              onClick={onReset}
              type="button"
              className="h-8 px-2 text-xs text-muted-foreground"
            >
              Reset
            </Button>
          </div>

          <div className="min-h-0 overflow-y-auto rounded-lg border bg-background">
            <ul className="divide-y">
              {orderedCategories.map((option) => {
                const isActive = option === category
                const itemClassName = [
                  "flex w-full items-center justify-between gap-3 px-3 py-2 text-left text-sm",
                  "transition-colors",
                  isActive ? "bg-primary/10" : "hover:bg-primary/10",
                ].join(" ")
                const indicatorClassName = [
                  "h-4 w-1 rounded-full",
                  isActive ? "bg-primary" : "bg-transparent",
                ].join(" ")

                return (
                  <li key={option}>
                    <button
                      type="button"
                      onClick={() => onCategoryChange(option)}
                      className={itemClassName}
                    >
                      <div className="flex items-center gap-2">
                        <span className={indicatorClassName} aria-hidden="true" />
                        <span className={isActive ? "font-medium text-foreground" : "text-foreground"}>
                          {getCategoryLabel(option)}
                        </span>
                      </div>

                      <span className="inline-flex items-center rounded-full bg-muted px-2 py-0.5 text-[11px] text-muted-foreground">
                        {categoryCount(option)}
                      </span>
                    </button>
                  </li>
                )
              })}
            </ul>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
