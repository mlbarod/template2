import React, { useEffect, useRef } from "react";
import { LinkIcon } from "@heroicons/react/24/outline";
import { useTimelineSelectionStore } from "../store/useTimelineSelectionStore";

const columnWidths = {
  time: 120,
  logType: 100,
  changeType: 180,
  operator: 100,
  duration: 120,
  url: 80,
};

function TableHeader() {
  return (
    <div className="sticky top-0 z-10 bg-muted text-muted-foreground">
      <div className="flex text-xs font-semibold">
        <div
          style={{ width: `${columnWidths.time}px` }}
          className="px-2 py-2 text-center flex-shrink-0"
        >
          Time
        </div>
        <div
          style={{ width: `${columnWidths.logType}px` }}
          className="px-2 py-2 text-center flex-shrink-0"
        >
          LogType
        </div>
        <div
          style={{ width: `${columnWidths.changeType}px` }}
          className="px-2 py-2 text-center flex-shrink-0"
        >
          ChangeType
        </div>
        <div
          style={{ width: `${columnWidths.operator}px` }}
          className="px-2 py-2 text-center flex-shrink-0"
        >
          Operator
        </div>
        <div
          style={{ width: `${columnWidths.duration}px` }}
          className="px-2 py-2 text-center flex-shrink-0"
        >
          Duration
        </div>
        <div
          style={{ width: `${columnWidths.url}px` }}
          className="px-2 py-2 text-center flex-shrink-0"
        >
          URL
        </div>
      </div>
    </div>
  );
}

function FilterCheckboxes({ typeFilters, handleFilter }) {
  return (
    <div className="flex gap-3 flex-wrap mr-3">
      {Object.entries(typeFilters).map(([type, checked]) => (
        <label key={type} className="flex items-center gap-1 text-xs font-bold">
          <input
            type="checkbox"
            name={type}
            checked={checked}
            onChange={handleFilter}
            className="rounded border border-border"
          />
          {type.replace("_LOG", "")}
        </label>
      ))}
    </div>
  );
}

const fallbackLogTypeBadgeClass = () => "bg-muted text-foreground";

function DataRow({ row, isSelected, onSelect, getLogTypeBadgeClass }) {
  const baseClasses =
    "flex items-center cursor-pointer border-b border-border hover:bg-muted";
  const selectionClasses = isSelected
    ? "bg-primary/10 transition-colors duration-200"
    : "bg-card transition-colors duration-150";
  const resolveLogTypeBadgeClass =
    getLogTypeBadgeClass || fallbackLogTypeBadgeClass;
  const logTypeClass = resolveLogTypeBadgeClass(row.logType);

  const handleRowClick = () => {
    onSelect(isSelected ? null : row.id);
  };

  const handleUrlClick = (e) => {
    e.stopPropagation();
    if (row.url) {
      window.open(row.url, "_blank", "noopener,noreferrer");
    }
  };

  return (
    <div
      data-row-id={row.id}
      onClick={handleRowClick}
      className={`${baseClasses} ${selectionClasses}`}
    >
      <div
        style={{ width: `${columnWidths.time}px` }}
        className="px-2 py-2 text-xs text-center text-foreground flex-shrink-0"
      >
        {row.displayTimestamp}
      </div>
      <div
        style={{ width: `${columnWidths.logType}px` }}
        className="px-2 py-2 text-xs text-center text-foreground flex-shrink-0"
      >
        <span className={`inline-block rounded px-2 py-1 text-xs ${logTypeClass}`}>
          {row.logType}
        </span>
      </div>
      <div
        style={{ width: `${columnWidths.changeType}px` }}
        className="px-2 py-2 text-xs text-center text-foreground flex-shrink-0"
      >
        {row.info1}
      </div>
      <div
        style={{ width: `${columnWidths.operator}px` }}
        className="px-2 py-2 text-xs text-center text-foreground flex-shrink-0"
      >
        {row.info2}
      </div>
      <div
        style={{ width: `${columnWidths.duration}px` }}
        className="px-2 py-2 text-xs text-center text-foreground flex-shrink-0"
      >
        {row.duration}
      </div>
      <div
        style={{ width: `${columnWidths.url}px` }}
        className="px-2 py-2 text-xs text-center flex-shrink-0"
      >
        {row.url ? (
          <button
            onClick={handleUrlClick}
            className="inline-flex h-8 w-8 items-center justify-center rounded transition-colors hover:bg-muted"
            title="Open URL"
          >
            <LinkIcon className="h-4 w-4 text-primary" />
          </button>
        ) : (
          <span className="text-muted-foreground">-</span>
        )}
      </div>
    </div>
  );
}

export default function TimelineDataTable({
  data,
  typeFilters,
  handleFilter,
  getLogTypeBadgeClass,
}) {
  const { selectedRow, source, setSelectedRow } = useTimelineSelectionStore();
  const scrollContainerRef = useRef(null);
  const resolveLogTypeBadgeClass =
    getLogTypeBadgeClass || fallbackLogTypeBadgeClass;

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
        <FilterCheckboxes typeFilters={typeFilters} handleFilter={handleFilter} />
      </div>

      <div className="flex-1 overflow-hidden">
        {data.length === 0 ? (
          <div className="p-4 text-center text-sm text-muted-foreground">
            표시할 데이터가 없습니다.
          </div>
        ) : (
          <div className="h-full bg-card rounded-b-lg overflow-hidden border border-border">
            <TableHeader />
            <div
              ref={scrollContainerRef}
              className="h-full overflow-auto"
              role="list"
            >
              {data.map((row) => (
                <DataRow
                  key={row.id}
                  row={row}
                  isSelected={String(row.id) === String(selectedRow)}
                  onSelect={handleSelect}
                  getLogTypeBadgeClass={resolveLogTypeBadgeClass}
                />
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
