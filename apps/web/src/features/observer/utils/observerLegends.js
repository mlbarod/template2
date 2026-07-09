import { OBSERVER_COLOR_CLASSES } from "./observerColorClasses";
import { ESOP_CHANGE_TYPE_LEGENDS } from "./esopChangeTypes";

export const observerLegends = {
  EQP: [
    { key: "RUN", className: OBSERVER_COLOR_CLASSES.EQP_RUN, label: "RUN" },
    { key: "DOWN", className: OBSERVER_COLOR_CLASSES.EQP_DOWN, label: "DOWN" },
    { key: "PM", className: OBSERVER_COLOR_CLASSES.EQP_PM, label: "PM" },
    { key: "IDLE", className: OBSERVER_COLOR_CLASSES.EQP_IDLE, label: "IDLE" },
    { key: "LOCAL", className: OBSERVER_COLOR_CLASSES.EQP_LOCAL, label: "LOCAL" },
  ],
  TIP: [
    { key: "OPEN", className: OBSERVER_COLOR_CLASSES.TIP_OPEN, label: "OPEN" },
    { key: "CLOSE", className: OBSERVER_COLOR_CLASSES.TIP_CLOSE, label: "CLOSE" },
  ],
  CTTTM: [
    { key: "CBM", className: OBSERVER_COLOR_CLASSES.CTTTM_CBM, label: "CBM" },
    { key: "NSP", className: OBSERVER_COLOR_CLASSES.CTTTM_NSP, label: "NSP" },
  ],
  RACB: [{ key: "RACB", className: OBSERVER_COLOR_CLASSES.RACB, label: "RACB" }],
  ESOP: ESOP_CHANGE_TYPE_LEGENDS,
};

export const getObserverLegend = (logType) => observerLegends[logType] || [];
