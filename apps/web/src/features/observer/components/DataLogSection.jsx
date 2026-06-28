// src/features/observer/components/DataLogSection.jsx
import React from "react";
import ObserverDataTable from "./ObserverDataTable";
import { LoadingSpinner } from "./Loaders";
import { getLogTypeBadgeClass } from "../utils/logTypeStyles";

export default function DataLogSection({
  eqpId,
  logsLoading,
  tableData,
  typeFilters,
  handleFilter,
  logErrors = [],
  onRetryLogs,
}) {
  const hasLogErrors = logErrors.length > 0;

  return (
    <section className="border border-border bg-card shadow-sm rounded-xl p-3 flex-[2] h-120 min-h-0 flex flex-col overflow-hidden">
      {!eqpId && !logsLoading ? (
        <p className="text-center text-sm text-muted-foreground py-4">
          EQP를 선택하세요.
        </p>
      ) : logsLoading ? (
        <div className="flex items-center justify-center h-full">
          <LoadingSpinner />
        </div>
      ) : (
        <>
          {hasLogErrors ? (
            <div className="mb-2 flex items-center justify-between gap-3 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-xs text-destructive">
              <span>
                {logErrors.map((error) => error.type).join(", ")} 로그 조회에 실패했습니다.
              </span>
              {onRetryLogs ? (
                <button
                  type="button"
                  onClick={onRetryLogs}
                  className="shrink-0 rounded border border-destructive/30 px-2 py-1 font-medium hover:bg-destructive/10"
                >
                  재시도
                </button>
              ) : null}
            </div>
          ) : null}
          <div className="min-h-0 flex-1">
            <ObserverDataTable
              data={tableData}
              typeFilters={typeFilters}
              handleFilter={handleFilter}
              getLogTypeBadgeClass={getLogTypeBadgeClass}
            />
          </div>
        </>
      )}
    </section>
  );
}
