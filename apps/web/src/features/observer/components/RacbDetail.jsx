// 파일 경로: src/features/observer/components/logDetail/RacbDetail.jsx
import React from "react";
import Field from "./Field";

export default function RacbDetail({ log }) {
  return (
    <>
      <Field label="Log Type" value={log.logType} />
      <Field label="RACB Alarm" value={log.eventType} />
      <Field label="Time" value={log.eventTime} />
      <Field label="Operator" value={log.operator} />
      <Field label="Line" value={log.lineId} />
      <Field label="EQP" value={log.eqpId} />
      <Field label="Comment" value={log.comment} fullWidth />
    </>
  );
}
