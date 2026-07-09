import { groupConfig } from "./observerMeta";
import { OBSERVER_COLOR_CLASSES } from "./observerColorClasses";
import { getContinuousRangeEnd } from "./logs";

const FALLBACK_CLASS = OBSERVER_COLOR_CLASSES.FALLBACK;

function getItemLabel(logType, log) {
  if (logType === "ESOP") return log.lotId || log.eventType;
  return log.eventType;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function buildItemTitle(log) {
  return [
    log.comment,
    log.operator ? `👤 ${log.operator}` : null,
    log.url ? `🔗 ${log.url}` : null,
  ]
    .filter(Boolean)
    .map(escapeHtml)
    .join("\n");
}

export function processData(logType, data, makeRangeContinuous = false) {
  const cfg = groupConfig[logType];
  if (!cfg) return [];

  const typeClass = `observer-type-${String(logType || "").toLowerCase()}`;
  const sortedData = data
    .filter((log) => log && log.eventTime)
    .sort((a, b) => new Date(a.eventTime) - new Date(b.eventTime));

  return sortedData.map((log, index) => {
    const start = new Date(log.eventTime);
    const end = makeRangeContinuous
      ? new Date(log.endTime || getContinuousRangeEnd(start, sortedData, index))
      : start;
    const stateClass =
      (cfg.stateClasses && cfg.stateClasses[log.eventType]) ||
      cfg.defaultClass ||
      FALLBACK_CLASS;
    const labelClass = `observer-item-label ${typeClass}`;
    const content = `<span class="${labelClass}">${escapeHtml(
      getItemLabel(logType, log)
    )}</span>`;

    return {
      id: log.id,
      group: logType,
      content,
      start,
      end,
      type: makeRangeContinuous ? "range" : "point",
      className: `observer-item ${typeClass} ${stateClass}`,
      title: buildItemTitle(log),
    };
  });
}
