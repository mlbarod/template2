// src/features/timeline/components/TipTimeline.jsx
import React from "react";
import BaseTimeline from "./BaseTimeline";
import TimelineLegend from "./TimelineLegend";
import TimelineEmptyState from "./TimelineEmptyState";
import { buildFixedHeightOptions } from "../utils/timelineUtils";
import {
  buildTipTimelineData,
  getTipTimelineHeight,
} from "../utils/tipTimelineGroups";
import { timelineLegends } from "../utils/timelineLegends";

export default function TipTimeline({
  tipLogs = [],
  totalTipLogCount,
  range,
  showLegend,
  showTimeAxis = true,
}) {
  const totalCount =
    typeof totalTipLogCount === "number" ? totalTipLogCount : tipLogs.length;
  const hasAnyTipLogs = totalCount > 0;
  const hasVisibleTipLogs = tipLogs.length > 0;

  const { groups, items } = buildTipTimelineData(tipLogs);
  const calculatedHeight = getTipTimelineHeight(groups);

  const options = buildFixedHeightOptions(range, calculatedHeight, {
    groupHeightMode: "fixed",
  });

  if (!hasAnyTipLogs || !hasVisibleTipLogs) {
    return (
      <TimelineEmptyState
        title="🔧 TIP 로그"
        headerNote={!hasAnyTipLogs ? "로그 없음" : "선택된 그룹 없음"}
        message={!hasAnyTipLogs ? "TIP 로그가 없습니다" : "표시할 TIP 그룹을 선택하세요"}
      />
    );
  }

  return (
    <BaseTimeline
      key={`tip-timeline-${groups.length}`}
      groups={groups}
      items={items}
      options={options}
      title={`🔧 TIP 로그 (${groups.length}개 그룹)`}
      showTimeAxis={showTimeAxis}
      className="tip-timeline"
      headerExtra={
        showLegend ? <TimelineLegend items={timelineLegends.TIP} /> : null
      }
    />
  );
}
