import { makeTipGroupLabel } from "./groupLabel";
import { getTipGroupKey } from "./tipUtils";
import { processData } from "./visTimelineItems";

export const TIP_GROUP_HEIGHT = 28;
export const TIP_TIME_AXIS_HEIGHT = 46;

export function buildTipTimelineData(tipLogs) {
  const groupMap = new Map();
  const groupedLogs = new Map();

  tipLogs.forEach((log) => {
    const groupKey = `TIP_${getTipGroupKey(log)}`;

    if (!groupMap.has(groupKey)) {
      groupMap.set(groupKey, {
        id: groupKey,
        content: makeTipGroupLabel(log.process, log.step, log.ppid),
        className: "custom-group-label tip-group",
        order: 100 + groupMap.size,
        title: `Line: ${log.lineId || "N/A"} | Process: ${
          log.process || "N/A"
        } | Step: ${log.step || "N/A"} | PPID: ${log.ppid || "N/A"}`,
      });
    }

    if (!groupedLogs.has(groupKey)) {
      groupedLogs.set(groupKey, []);
    }
    groupedLogs.get(groupKey).push(log);
  });

  const groups = Array.from(groupMap.values()).sort(
    (first, second) => first.order - second.order
  );
  const items = [];

  groupedLogs.forEach((logs, groupKey) => {
    const processed = processData("TIP", logs, true);
    processed.forEach((item) => {
      items.push({ ...item, group: groupKey });
    });
  });

  return { groups, items };
}

export function getTipTimelineHeight(groups) {
  if (groups.length === 0) return TIP_TIME_AXIS_HEIGHT;
  return TIP_GROUP_HEIGHT * groups.length + TIP_TIME_AXIS_HEIGHT;
}
