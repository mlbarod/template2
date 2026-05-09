import React from "react";
import { timelineTableColumnWidths } from "./timelineTableColumns";

export default function TimelineTableHeader() {
  return (
    <div className="sticky top-0 z-10 bg-muted text-muted-foreground">
      <div className="flex text-xs font-semibold">
        <div
          style={{ width: `${timelineTableColumnWidths.time}px` }}
          className="px-2 py-2 text-center flex-shrink-0"
        >
          Time
        </div>
        <div
          style={{ width: `${timelineTableColumnWidths.logType}px` }}
          className="px-2 py-2 text-center flex-shrink-0"
        >
          LogType
        </div>
        <div
          style={{ width: `${timelineTableColumnWidths.changeType}px` }}
          className="px-2 py-2 text-center flex-shrink-0"
        >
          ChangeType
        </div>
        <div
          style={{ width: `${timelineTableColumnWidths.operator}px` }}
          className="px-2 py-2 text-center flex-shrink-0"
        >
          Operator
        </div>
        <div
          style={{ width: `${timelineTableColumnWidths.duration}px` }}
          className="px-2 py-2 text-center flex-shrink-0"
        >
          Duration
        </div>
        <div
          style={{ width: `${timelineTableColumnWidths.url}px` }}
          className="px-2 py-2 text-center flex-shrink-0"
        >
          URL
        </div>
      </div>
    </div>
  );
}
