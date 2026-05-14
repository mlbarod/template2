import { groupConfig } from "./timelineMeta";

const FALLBACK_CLASS = "timeline-color-fallback";

function buildRangeEnd(start, sortedData, index) {
  if (index < sortedData.length - 1) {
    return new Date(sortedData[index + 1].eventTime);
  }

  const now = new Date();
  const todayMidnight = new Date(
    now.getFullYear(),
    now.getMonth(),
    now.getDate(),
    0,
    0,
    0,
    0
  );

  if (start < todayMidnight) {
    return todayMidnight;
  }
  return new Date(start.getTime() + 60 * 60 * 1000);
}

export function processData(logType, data, makeRangeContinuous = false) {
  const cfg = groupConfig[logType];
  if (!cfg) return [];

  const typeClass = `timeline-type-${String(logType || "").toLowerCase()}`;
  const sortedData = data
    .filter((log) => log && log.eventTime)
    .sort((a, b) => new Date(a.eventTime) - new Date(b.eventTime));

  return sortedData.map((log, index) => {
    const start = new Date(log.eventTime);
    const end = makeRangeContinuous
      ? buildRangeEnd(start, sortedData, index)
      : start;
    const stateClass =
      (cfg.stateClasses && cfg.stateClasses[log.eventType]) ||
      cfg.defaultClass ||
      FALLBACK_CLASS;
    const labelClass = `timeline-item-label ${typeClass}`;
    const content = `<span class="${labelClass}">${log.eventType || ""}</span>`;

    return {
      id: log.id,
      group: logType,
      content,
      start,
      end,
      type: makeRangeContinuous ? "range" : "point",
      className: `timeline-item ${typeClass} ${stateClass}`,
      title: [
        log.comment,
        log.operator ? `👤 ${log.operator}` : null,
        log.url ? `🔗 ${log.url}` : null,
      ]
        .filter(Boolean)
        .join("\n"),
    };
  });
}
