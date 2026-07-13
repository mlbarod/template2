// 파일 경로: src/features/l3-spider/api/queryKeys.js
// L3 Spider React Query 키 정의

export const l3SpiderQueryKeys = {
  all: ["l3-spider"],
  meta: () => ["l3-spider", "meta"],
  unmappedLineRules: () => ["l3-spider", "developer", "unmapped-line-rules"],
  structure: (selectionKey) => ["l3-spider", "structure", selectionKey],
  stats: (selectionKey) => ["l3-spider", "stats", selectionKey],
  exclusionFilters: () => ["l3-spider", "exclusion-filters"],
  mailRules: () => ["l3-spider", "mail-rules"],
  summary: (selectionKey) => ["l3-spider", "summary", selectionKey],
  dailySummary: (dateKey) => ["l3-spider", "daily-summary", dateKey],
  data: (selectionKey, filterKey) => ["l3-spider", "data", selectionKey, filterKey],
  filterCandidates: (key) => ["l3-spider", "filter-candidates", key],
  trend: () => ["l3-spider", "trend"],
}
