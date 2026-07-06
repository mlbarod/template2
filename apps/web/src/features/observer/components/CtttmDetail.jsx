// 파일 경로: src/features/observer/components/logDetail/CtttmDetail.jsx
import React from "react";
import { ExternalLink } from "lucide-react";
import Field from "./Field";

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

function formatSummaryTimestamp(text) {
  if (typeof text !== "string") return text;

  return text.replace(
    /\[(\d{2})(\d{2})-(\d{2})-(\d{2}) (\d{2}:\d{2})\]/g,
    "[$2/$3/$4 $5]"
  );
}

export default function CtttmDetail({ log }) {
  return (
    <>
      <Field label="Log Type" value={log.logType} />
      <Field label="CTTTM" value={log.eventType} />
      <Field label="Time" value={log.eventTime} />
      <Field label="Operator" value={log.operator} />
      <Field
        label="Title"
        value={log.comment}
      />
      <Field
        label="URL"
        value={log.url ? <CtttmUrlLink url={log.url} /> : null}
      />
      <Field
        label="Summary"
        value={formatSummaryTimestamp(log.summary)}
        fullWidth
        streaming={true}
        streamingClassName="leading-6"
      />
    </>
  );
}
