// src/features/observer/components/logDetail/Field.jsx
import React from "react";
import StreamingText from "./StreamingText";

const TIME_FIELD_LABELS = new Set(["Time", "End Time"]);

function formatDetailDateTime(value) {
  if (typeof value !== "string") return value;

  const match = value.trim().match(/^(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2}:\d{2})(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?$/);
  if (!match) return value;

  return `${match[1]} ${match[2]}`;
}

/**
 * 필드 공통 출력 컴포넌트
 */
export default function Field({
  label,
  value,
  className = "",
  valueClassName = "",
  fullWidth = false,
  streaming = false,
}) {
  const displayValue = TIME_FIELD_LABELS.has(label) ? formatDetailDateTime(value) : value;
  const content = streaming ? <StreamingText text={displayValue || "-"} /> : displayValue || "-";

  if (fullWidth) {
    return (
      <div
        className={`col-span-4 grid grid-cols-[max-content_minmax(0,1fr)] gap-x-4 gap-y-1 ${className}`}
      >
        <div className="font-semibold text-foreground">
          {label}
        </div>
        <div className={`min-w-0 break-words ${valueClassName}`}>
          {content}
        </div>
      </div>
    );
  }

  return (
    <>
      <div
        className={`font-semibold text-foreground ${className}`}
      >
        {label}
      </div>
      <div className={`min-w-0 break-words ${valueClassName}`}>
        {content}
      </div>
    </>
  );
}
