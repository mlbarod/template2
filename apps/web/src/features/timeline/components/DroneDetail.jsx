import React from "react";
import Field from "./Field";

export default function DroneDetail({ log }) {
  return (
    <>
      <Field label="ID" value={log.id} />
      <Field label="Log Type" value={log.logType} />
      <Field label="Sample Type" value={log.eventType} />
      <Field label="Status" value={log.status} />
      <Field label="Time" value={log.eventTime} />
      <Field label="Operator" value={log.operator} />
      <Field label="Line" value={log.lineId} />
      <Field label="EQP" value={log.eqpId} />
      <Field label="Comment" value={log.comment} className="col-span-2" />
    </>
  );
}
