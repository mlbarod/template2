// 파일 경로: src/features/observer/components/logDetail/CtttmDetail.jsx
import React from "react";
import { ExternalLink } from "lucide-react";
import Field from "./Field";

const FULL_WIDTH_LABEL_CLASS = "leading-6";
const FULL_WIDTH_VALUE_CONTAINER_CLASS = "w-full max-w-[calc(100vw-8rem)]";
const FULL_WIDTH_TEXT_CLASS = "whitespace-pre-wrap break-words leading-6";
const FULL_WIDTH_STREAMING_SCROLL_CLASS = "max-w-full whitespace-pre-wrap break-words overflow-visible";

function CtttmUrlLink({ url }) {
  return (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      className="inline-flex items-baseline gap-1 align-baseline text-primary transition-colors hover:text-primary/80 focus:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1"
      title={url}
      aria-label="CTTTM URL 새 탭에서 열기"
    >
      <span className="font-semibold">LINK</span>
      <ExternalLink className="inline size-[1em]" />
    </a>
  );
}

function normalizeDetailText(text) {
  if (typeof text !== "string") return text;

  return text.trim();
}

function formatSummaryTimestamp(text) {
  if (typeof text !== "string") return text;

  return normalizeDetailText(text).replace(
    /\[(\d{2})(\d{2})-(\d{2})-(\d{2}) (\d{2}:\d{2})\]/g,
    "[$2/$3/$4 $5]"
  );
}

export default function CtttmDetail({
  log,
  summaryStreamingScrollClassName,
  onStreamingProgress,
}) {
  return (
    <>
      <Field label="Log Type" value={log.logType} />
      <Field label="CTTTM" value={log.eventType} />
      <Field label="Time" value={log.eventTime} />
      <Field
        label="URL"
        value={log.url ? <CtttmUrlLink url={log.url} /> : null}
      />
      <Field
        label="Title"
        value={normalizeDetailText(log.comment)}
        fullWidth
        className={FULL_WIDTH_LABEL_CLASS}
        valueContainerClassName={FULL_WIDTH_VALUE_CONTAINER_CLASS}
        valueClassName={FULL_WIDTH_TEXT_CLASS}
      />
      <Field
        label="핵심요약"
        value={normalizeDetailText(log.coreSummary)}
        fullWidth
        streaming={true}
        className={FULL_WIDTH_LABEL_CLASS}
        valueContainerClassName={FULL_WIDTH_VALUE_CONTAINER_CLASS}
        valueClassName={FULL_WIDTH_TEXT_CLASS}
        streamingClassName="leading-6"
        streamingScrollClassName={FULL_WIDTH_STREAMING_SCROLL_CLASS}
        onStreamingProgress={onStreamingProgress}
      />
      <Field
        label="Summary"
        value={formatSummaryTimestamp(log.summary)}
        fullWidth
        streaming={true}
        className={FULL_WIDTH_LABEL_CLASS}
        valueContainerClassName={FULL_WIDTH_VALUE_CONTAINER_CLASS}
        valueClassName={FULL_WIDTH_TEXT_CLASS}
        streamingClassName="leading-6 tabular-nums"
        streamingScrollClassName={`${FULL_WIDTH_STREAMING_SCROLL_CLASS} ${summaryStreamingScrollClassName || ""}`}
        onStreamingProgress={onStreamingProgress}
      />
    </>
  );
}
