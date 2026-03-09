// 파일 경로: src/features/line-dashboard/utils/lineFilterMode.js
// 라인 필터 모드 상수/옵션/정규화 규칙을 한 곳에서 관리합니다.

export const LINE_FILTER_MODE_TARGET_USER_SDWT = "target_user_sdwt_prod"
export const LINE_FILTER_MODE_USER_SDWT = "user_sdwt_prod"
export const LINE_FILTER_MODE_SDWT = "sdwt_prod"

export const DEFAULT_LINE_FILTER_MODE = LINE_FILTER_MODE_TARGET_USER_SDWT

const LINE_FILTER_MODE_SET = new Set([
  LINE_FILTER_MODE_TARGET_USER_SDWT,
  LINE_FILTER_MODE_USER_SDWT,
  LINE_FILTER_MODE_SDWT,
])

export const LINE_FILTER_MODE_OPTIONS = [
  {
    value: LINE_FILTER_MODE_TARGET_USER_SDWT,
    labelKey: "lineFilterModeTargetUserSdwt",
    descriptionKey: "lineFilterModeTargetUserSdwtDescription",
  },
  {
    value: LINE_FILTER_MODE_USER_SDWT,
    labelKey: "lineFilterModeUserSdwt",
    descriptionKey: "lineFilterModeUserSdwtDescription",
  },
  {
    value: LINE_FILTER_MODE_SDWT,
    labelKey: "lineFilterModeSdwt",
    descriptionKey: "lineFilterModeSdwtDescription",
  },
]

export function normalizeLineFilterMode(value) {
  if (typeof value !== "string") return DEFAULT_LINE_FILTER_MODE
  const normalized = value.trim()
  return LINE_FILTER_MODE_SET.has(normalized) ? normalized : DEFAULT_LINE_FILTER_MODE
}
