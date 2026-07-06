// Observer log detail의 label/value 표시 컴포넌트입니다.
import React from "react";
import StreamingText from "./StreamingText";

const TIME_FIELD_LABELS = new Set(["Time", "End Time"]);

function formatDetailDateTime(value) {
  if (typeof value !== "string") return value;

  const match = value.trim().match(/^(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2}:\d{2})(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?$/);
  if (!match) return value;

  return `${match[1]} ${match[2]}`;
}

function FieldLabel({ label, className = "" }) {
  return (
    <div
      className={`grid grid-cols-[minmax(0,1fr)_max-content] gap-x-1 font-semibold text-foreground ${className}`}
    >
      <span className="min-w-0">{label}</span>
      <span>:</span>
    </div>
  );
}

/**
 * 필드 공통 출력 컴포넌트
 */
export default function Field({
  label,
  value,
  className = "",
  valueClassName = "",
  valueContainerClassName = "",
  fullWidth = false,
  streaming = false,
  streamingActive = true,
  streamingClassName = "",
  streamingScrollClassName = undefined,
  onStreamingProgress,
  onStreamingComplete,
}) {
  const displayValue = TIME_FIELD_LABELS.has(label) ? formatDetailDateTime(value) : value;
  const content = streaming ? (
    <StreamingText
      text={displayValue || "-"}
      className={streamingClassName}
      scrollClassName={streamingScrollClassName}
      active={streamingActive}
      onProgress={onStreamingProgress}
      onComplete={onStreamingComplete}
    />
  ) : displayValue || "-";

  if (fullWidth) {
    return (
      <>
        <FieldLabel label={label} className={`col-start-1 ${className}`} />
        <div className={`col-start-2 col-end-5 min-w-0 break-words ${valueContainerClassName} ${valueClassName}`}>
          {content}
        </div>
      </>
    );
  }

  return (
    <>
      <FieldLabel label={label} className={className} />
      <div className={`min-w-0 break-words ${valueContainerClassName} ${valueClassName}`}>
        {content}
      </div>
    </>
  );
}
