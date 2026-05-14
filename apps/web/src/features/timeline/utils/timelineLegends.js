export const timelineLegends = {
  EQP: [
    { key: "RUN", className: "timeline-color-eqp-run", label: "RUN" },
    { key: "DOWN", className: "timeline-color-eqp-down", label: "DOWN" },
    { key: "PM", className: "timeline-color-eqp-pm", label: "PM" },
    { key: "IDLE", className: "timeline-color-eqp-idle", label: "IDLE" },
    { key: "LOCAL", className: "timeline-color-eqp-local", label: "LOCAL" },
  ],
  TIP: [
    { key: "OPEN", className: "timeline-color-tip-open", label: "OPEN" },
    { key: "CLOSE", className: "timeline-color-tip-close", label: "CLOSE" },
  ],
  CTTTM: [
    { key: "CBM", className: "timeline-color-ctttm-cbm", label: "CBM" },
    { key: "NSP", className: "timeline-color-ctttm-nsp", label: "NSP" },
  ],
  RACB: [
    { key: "ALARM", className: "timeline-color-racb-alarm", label: "ALARM" },
    { key: "WARN", className: "timeline-color-racb-warn", label: "WARN" },
  ],
  DRONE: [
    { key: "DRONE", className: "timeline-color-drone", label: "DRONE" },
  ],
};

export const getTimelineLegend = (logType) => timelineLegends[logType] || [];
