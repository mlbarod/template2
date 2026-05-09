// 파일 경로: src/features/voc/utils/constants.js
// VOC 화면에서 공유하는 상태 상수

export const STATUS_OPTIONS = [
  {
    value: "접수",
    tone:
      "border-sky-200 bg-sky-50 text-sky-800 dark:border-sky-800 dark:bg-sky-900/40 dark:text-sky-50",
  },
  {
    value: "진행중",
    tone:
      "border-amber-200 bg-amber-50 text-amber-800 dark:border-amber-800 dark:bg-amber-900/40 dark:text-amber-50",
  },
  {
    value: "완료",
    tone:
      "border-emerald-200 bg-emerald-50 text-emerald-800 dark:border-emerald-800 dark:bg-emerald-900/35 dark:text-emerald-50",
  },
  {
    value: "반려",
    tone:
      "border-rose-200 bg-rose-50 text-rose-800 dark:border-rose-800 dark:bg-rose-900/40 dark:text-rose-50",
  },
]

export const DEFAULT_STATUS = STATUS_OPTIONS[0]?.value || "접수"

// VOC 앱 카테고리(정적 목록). 항목 추가 시 value/label을 함께 등록하고 VocPost.AppCategory와 값을 맞추세요.
export const APP_CATEGORIES = [
  {
    value: "기타",
    label: "기타",
  },
]

export const DEFAULT_APP_CATEGORY = APP_CATEGORIES[0]?.value || "기타"

// VOC 리치 텍스트 에디터 설정. 콘텐츠 정화/렌더링 정책은 utils/index.js에서만 관리합니다.
export const RICH_TEXT_EDITOR_MODULES = {
  toolbar: [
    [{ header: [1, 2, 3, false] }],
    ["bold", "italic", "underline", "strike"],
    [{ color: [] }, { background: [] }],
    [{ list: "ordered" }, { list: "bullet" }],
    [{ align: [] }],
    ["link", "image"],
  ],
  clipboard: {
    matchVisual: false,
  },
}

export const RICH_TEXT_EDITOR_FORMATS = [
  "header",
  "bold",
  "italic",
  "underline",
  "strike",
  "color",
  "background",
  "list",
  "bullet",
  "align",
  "link",
  "image",
]
