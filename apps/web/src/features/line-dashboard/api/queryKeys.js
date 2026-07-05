// 파일 경로: src/features/line-dashboard/api/queryKeys.js
// 라인 대시보드 관련 서버 상태에서 공유할 React Query 키 모음입니다.
// - feature 내부/외부에서 invalidateQuery 등에 재사용할 수 있도록 헬퍼 형태로 정의합니다.

const ROOT_KEY = ["line-dashboard"]

export const lineDashboardQueryKeys = {
  all: ROOT_KEY,
  lineOptions: () => [...ROOT_KEY, "line-options"],
  lineSdwtOptions: () => [...ROOT_KEY, "line-sdwt-options"],
  droneTargetAdmin: () => [...ROOT_KEY, "admin", "drone-targets"],
  jiraUserSdwtProds: () => [...ROOT_KEY, "jira-user-sdwt-prods"],
  summary: (lineId) => [...ROOT_KEY, "summary", lineId ?? null],
  history: (lineId, range = {}) => [
    ...ROOT_KEY,
    "history",
    {
      lineId: lineId ?? null,
      from: range.from ?? null,
      to: range.to ?? null,
    },
  ],
  table: (params = {}) => [
    ...ROOT_KEY,
    "table",
    {
      table: params.table ?? null,
      lineId: params.lineId ?? null,
      lineFilterMode: params.lineFilterMode ?? null,
      from: params.from ?? null,
      to: params.to ?? null,
      recentHoursStart: params.recentHoursStart ?? null,
      recentHoursEnd: params.recentHoursEnd ?? null,
    },
  ],
}
