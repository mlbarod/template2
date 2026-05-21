// 파일 경로: src/features/l3-spider/api/queryKeys.js
// L3 Spider React Query 키 정의

export const l3SpiderQueryKeys = {
  all: ["l3-spider"],
  meta: () => ["l3-spider", "meta"],
  summary: (selectionKey) => ["l3-spider", "summary", selectionKey],
  data: (selectionKey, filterKey) => ["l3-spider", "data", selectionKey, filterKey],
}
