import { ESOP_CHANGE_TYPE_LEGENDS } from "./esopChangeTypes";

export const observerLegends = {
  EQP: [
    { key: "RUN", className: "observer-color-eqp-run", label: "RUN" },
    { key: "DOWN", className: "observer-color-eqp-down", label: "DOWN" },
    { key: "PM", className: "observer-color-eqp-pm", label: "PM" },
    { key: "IDLE", className: "observer-color-eqp-idle", label: "IDLE" },
    { key: "LOCAL", className: "observer-color-eqp-local", label: "LOCAL" },
  ],
  TIP: [
    { key: "OPEN", className: "observer-color-tip-open", label: "OPEN" },
    { key: "CLOSE", className: "observer-color-tip-close", label: "CLOSE" },
  ],
  CTTTM: [
    { key: "CBM", className: "observer-color-ctttm-cbm", label: "CBM" },
    { key: "NSP", className: "observer-color-ctttm-nsp", label: "NSP" },
  ],
  RACB: [
    { key: "ALARM", className: "observer-color-racb-alarm", label: "ALARM" },
    { key: "WARN", className: "observer-color-racb-warn", label: "WARN" },
  ],
  ESOP: ESOP_CHANGE_TYPE_LEGENDS,
};

export const getObserverLegend = (logType) => observerLegends[logType] || [];
