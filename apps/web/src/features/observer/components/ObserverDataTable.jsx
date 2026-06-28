import React, { useEffect, useRef } from "react";
import { useObserverSelectionStore } from "../store/useObserverSelectionStore";
import ObserverTableHeader from "./table/ObserverTableHeader";
import ObserverTableFilters from "./table/ObserverTableFilters";
import ObserverTableRow from "./table/ObserverTableRow";

export default function ObserverDataTable({
  data,
  typeFilters,
  handleFilter,
  getLogTypeBadgeClass,
}) {
  const { selectedRow, source, setSelectedRow } = useObserverSelectionStore();
  const scrollContainerRef = useRef(null);
  useEffect(() => {
    if (source !== "observer" || !selectedRow) return;
    const container = scrollContainerRef.current;
    if (!container) return;

    const target = container.querySelector(
      `[data-row-id="${String(selectedRow)}"]`
    );
    if (!target) return;

    const containerRect = container.getBoundingClientRect();
    const targetRect = target.getBoundingClientRect();
    const offsetTop = targetRect.top - containerRect.top;
    const targetCenter = offsetTop + targetRect.height / 2;
    const scrollTarget =
      container.scrollTop + targetCenter - container.clientHeight / 2;

    container.scrollTo({
      top: Math.max(scrollTarget, 0),
      behavior: "smooth",
    });
  }, [selectedRow, source]);

  const handleSelect = (rowId) => setSelectedRow(rowId, "table");

  return (
    <div className="flex h-full min-h-0 flex-col overflow-hidden">
      <div className="flex justify-between items-center pt-1 bg-card text-foreground rounded-t-lg border-b border-border">
        <h3 className="text-md font-semibold mb-5">📜 Data Log</h3>
        <ObserverTableFilters
          typeFilters={typeFilters}
          handleFilter={handleFilter}
        />
      </div>

      <div className="min-h-0 flex-1 overflow-hidden">
        {data.length === 0 ? (
          <div className="p-4 text-center text-sm text-muted-foreground">
            표시할 데이터가 없습니다.
          </div>
        ) : (
          <div className="grid h-full min-h-0 grid-rows-[auto_1fr] overflow-hidden rounded-b-lg border border-border bg-card">
            <ObserverTableHeader />
            <div
              ref={scrollContainerRef}
              className="min-h-0 overflow-auto"
              role="listbox"
              aria-label="Observer 로그 목록"
            >
              {data.map((row) => (
                <ObserverTableRow
                  key={row.id}
                  row={row}
                  isSelected={String(row.id) === String(selectedRow)}
                  onSelect={handleSelect}
                  getLogTypeBadgeClass={getLogTypeBadgeClass}
                />
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
