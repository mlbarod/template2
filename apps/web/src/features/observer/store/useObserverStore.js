import { create } from "zustand"

const RANGE_SYNC_TOLERANCE_MS = 1

function shouldSkipRangeSync(observer, start, end) {
  if (!observer?.getWindow) return false

  const current = observer.getWindow()
  const currentStart = new Date(current.start).getTime()
  const currentEnd = new Date(current.end).getTime()
  const nextStart = new Date(start).getTime()
  const nextEnd = new Date(end).getTime()

  if ([currentStart, currentEnd, nextStart, nextEnd].some(Number.isNaN)) {
    return false
  }

  return (
    Math.abs(currentStart - nextStart) <= RANGE_SYNC_TOLERANCE_MS &&
    Math.abs(currentEnd - nextEnd) <= RANGE_SYNC_TOLERANCE_MS
  )
}

export const useObserverStore = create((set, get) => ({
  /* —— Observer 전용 상태 —— */
  showLegend: true,
  selectedTipGroups: ["__ALL__"],

  /* —— Observer 상태 변경 액션 —— */
  setShowLegend: (show) => set({ showLegend: show }),
  toggleShowLegend: () => set((state) => ({ showLegend: !state.showLegend })),
  setSelectedTipGroups: (groups) => set({ selectedTipGroups: groups }),

  /* —— vis-timeline 인스턴스 풀 관리 —— */
  pool: [],
  register: (tl) => set((s) => ({ pool: [...s.pool, tl] })),
  unregister: (tl) => set((s) => ({ pool: s.pool.filter((t) => t !== tl) })),

  syncRange: (self, start, end) => {
    const { pool } = get()
    pool.forEach((tl) => {
      if (tl === self || shouldSkipRangeSync(tl, start, end)) return
      tl.setWindow(start, end, { animation: false })
    })
  },
}))
