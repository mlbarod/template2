// 파일 경로: src/features/pm-spider/api/queryKeys.js
// PM SPIDER React Query 키 정의입니다.

export const pmSpiderQueryKeys = {
  all: ["pm-spider"],
  meta: (selectionKey = "all") => ["pm-spider", "meta", selectionKey],
  result: (payloadKey) => ["pm-spider", "result", payloadKey],
  category: (pattern, payloadKey) => ["pm-spider", "category", pattern, payloadKey],
  detail: (categoryId, itemKey, payloadKey) => [
    "pm-spider",
    "detail",
    categoryId,
    itemKey,
    payloadKey,
  ],
}
