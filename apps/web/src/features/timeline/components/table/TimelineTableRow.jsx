import React from "react";
import { LinkIcon } from "@heroicons/react/24/outline";
import { timelineTableColumnWidths } from "./timelineTableColumns";

const fallbackLogTypeBadgeClass = () => "bg-muted text-foreground";

export default function TimelineTableRow({
  row,
  isSelected,
  onSelect,
  getLogTypeBadgeClass,
}) {
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

  const handleUrlClick = (event) => {
    event.stopPropagation();
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
        style={{ width: `${timelineTableColumnWidths.time}px` }}
        className="px-2 py-2 text-xs text-center text-foreground flex-shrink-0"
      >
        {row.displayTimestamp}
      </div>
      <div
        style={{ width: `${timelineTableColumnWidths.logType}px` }}
        className="px-2 py-2 text-xs text-center text-foreground flex-shrink-0"
      >
        <span className={`inline-block rounded px-2 py-1 text-xs ${logTypeClass}`}>
          {row.logType}
        </span>
      </div>
      <div
        style={{ width: `${timelineTableColumnWidths.changeType}px` }}
        className="px-2 py-2 text-xs text-center text-foreground flex-shrink-0"
      >
        {row.info1}
      </div>
      <div
        style={{ width: `${timelineTableColumnWidths.operator}px` }}
        className="px-2 py-2 text-xs text-center text-foreground flex-shrink-0"
      >
        {row.info2}
      </div>
      <div
        style={{ width: `${timelineTableColumnWidths.duration}px` }}
        className="px-2 py-2 text-xs text-center text-foreground flex-shrink-0"
      >
        {row.duration}
      </div>
      <div
        style={{ width: `${timelineTableColumnWidths.url}px` }}
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
