// 파일 경로: src/features/observer/components/logDetail/TipDetail.jsx
import React from "react";
import Field from "./Field";

export default function TipDetail({ log }) {
  return (
    <>
      <Field label="Log Type" value={log.logType} />
      <Field label="TIP Event" value={log.eventType} />
      <Field label="Time" value={log.eventTime} />
      <Field label="Operator" value={log.operator} />
      <Field label="Line" value={log.lineId} />
      <Field label="Process" value={log.process} />
      <Field label="Step" value={log.step} />
      <Field label="PPID" value={log.ppid} />
      <Field label="Comment" value={log.comment} fullWidth />
    </>
  );
}
