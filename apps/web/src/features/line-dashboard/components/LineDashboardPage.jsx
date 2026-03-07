// src/features/line-dashboard/components/LineDashboardPage.jsx
import { DataTable } from "./DataTable"

// 라인별 컨텍스트를 구성하고 데이터 테이블을 감싸는 최상위 페이지 컴포넌트입니다.
export function LineDashboardPage({ lineId }) {
  return (
    <div className="flex h-full flex-col gap-4">
      <div className="flex-1 min-h-0">
        <DataTable lineId={lineId} />
      </div>
    </div>
  )
}
