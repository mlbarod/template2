import React, { useEffect, useRef } from "react";
import { useTimelineSelectionStore } from "../store/useTimelineSelectionStore";
import TimelineTableHeader from "./table/TimelineTableHeader";
import TimelineTableFilters from "./table/TimelineTableFilters";
import TimelineTableRow from "./table/TimelineTableRow";

export default function TimelineDataTable({
  data,
  typeFilters,
  handleFilter,
  getLogTypeBadgeClass,
}) {
  const { selectedRow, source, setSelectedRow } = useTimelineSelectionStore();
  const scrollContainerRef = useRef(null);
  useEffect(() => {
    if (source !== "timeline" || !selectedRow) return;
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
    <div className="h-full flex flex-col overflow-hidden">
      <div className="flex justify-between items-center pt-1 bg-card text-foreground rounded-t-lg border-b border-border">
        <h3 className="text-md font-semibold mb-5">📜 Data Log</h3>
        <TimelineTableFilters
          typeFilters={typeFilters}
          handleFilter={handleFilter}
        />
      </div>

      <div className="flex-1 overflow-hidden">
        {data.length === 0 ? (
          <div className="p-4 text-center text-sm text-muted-foreground">
            표시할 데이터가 없습니다.
          </div>
        ) : (
          <div className="h-full bg-card rounded-b-lg overflow-hidden border border-border">
            <TimelineTableHeader />
            <div
              ref={scrollContainerRef}
              className="h-full overflow-auto"
              role="list"
            >
              {data.map((row) => (
                <TimelineTableRow
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
