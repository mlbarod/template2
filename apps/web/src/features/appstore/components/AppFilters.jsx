// 앱스토어 필터 패널
import { Plus, Search, Star, X } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"

const ALL_CATEGORY = "all"
const CATEGORY_DISPLAY_ORDER = [
  "DX App",
  "Engineer App",
  "Etch Report",
  "PM Report",
  "품질 Report",
  "환경안전 Report",
  "생산지원 Report",
  "설치기술 Report",
  "E린이 필수 App",
]
const CATEGORY_ORDER_SET = new Set(CATEGORY_DISPLAY_ORDER)
const FEATURED_REPORT_CATEGORY = "Etch Report"

const getCategoryLabel = (option) => {
  if (option === ALL_CATEGORY) return "Total"
  return option
}
const getOrderedCategories = (categories) => {
  const categorySet = new Set(categories)

  return [
    ...CATEGORY_DISPLAY_ORDER.filter((option) => categorySet.has(option)),
    ...categories.filter(
      (option) => option !== ALL_CATEGORY && !CATEGORY_ORDER_SET.has(option),
    ),
  ]
}
const getCategorySections = (categories) => {
  const sections = [
    { title: "App", items: [] },
    { title: "Report", items: [] },
  ]
  const featuredItems = []
  const otherItems = []

  getOrderedCategories(categories).forEach((option) => {
    const normalizedOption = option.toLowerCase()

    if (option === FEATURED_REPORT_CATEGORY) {
      featuredItems.push(option)
      return
    }

    if (normalizedOption.includes("app")) {
      sections[0].items.push(option)
      return
    }

    if (normalizedOption.includes("report")) {
      sections[1].items.push(option)
      return
    }

    otherItems.push(option)
  })

  return [
    ...(featuredItems.length > 0 ? [{ title: "", items: featuredItems }] : []),
    ...sections.filter((section) => section.items.length > 0),
    ...(otherItems.length > 0 ? [{ title: "", items: otherItems }] : []),
  ]
}

function CategoryButton({ option, category, count, onCategoryChange }) {
  const isActive = option === category
  const isFeaturedReport = option === FEATURED_REPORT_CATEGORY
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
    <button
      type="button"
      onClick={() => onCategoryChange(option)}
      className={itemClassName}
    >
      <div className="flex min-w-0 items-center gap-2">
        <span className={indicatorClassName} aria-hidden="true" />
        <span className={isActive ? "truncate font-medium text-foreground" : "truncate text-foreground"}>
          {getCategoryLabel(option)}
        </span>
        {isFeaturedReport ? (
          <Star className="size-3 fill-primary text-primary" aria-label="주요 Report" />
        ) : null}
      </div>

      <span className="inline-flex items-center rounded-full bg-muted px-2 py-0.5 text-[11px] text-muted-foreground">
        {count}
      </span>
    </button>
  )
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
  const categorySections = getCategorySections(categories)
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
      <Card className="flex min-h-0 flex-col rounded-2xl border bg-card shadow-sm">
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

          <div className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-lg border bg-background">
            <div className="min-h-0 flex-1 overflow-y-auto">
              {categorySections.map((section, sectionIndex) => (
                <div key={section.title || "other"} className={sectionIndex > 0 ? "border-t" : ""}>
                  {section.title ? (
                    <div className="px-3 pb-1 pt-3 text-[11px] font-semibold text-muted-foreground">
                      {section.title}
                    </div>
                  ) : null}
                  <ul className="divide-y">
                    {section.items.map((option) => (
                      <li key={option}>
                        <CategoryButton
                          option={option}
                          category={category}
                          count={categoryCount(option)}
                          onCategoryChange={onCategoryChange}
                        />
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
            <div className="border-t">
              <CategoryButton
                option={ALL_CATEGORY}
                category={category}
                count={categoryCount(ALL_CATEGORY)}
                onCategoryChange={onCategoryChange}
              />
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
