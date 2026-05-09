// src/features/timeline/components/EqpTimeline.jsx
import React from "react";
import BaseTimeline from "./BaseTimeline";
import TimelineLegend from "./TimelineLegend";
import TimelineEmptyState from "./TimelineEmptyState";
import { buildFixedHeightOptions } from "../utils/timelineUtils";
import { processData } from "../utils/visTimelineItems";
import { makeGroupLabel } from "../utils/groupLabel";
import { timelineLegends } from "../utils/timelineLegends";

const EQP_GROUP = {
  id: "EQP",
  content: makeGroupLabel("EQP", "EQP 로그"),
  className: "custom-group-label",
  order: 1,
};

export default function EqpTimeline({
  range,
  showLegend,
  showTimeAxis = false,
  eqpLogs = [],
}) {
  const items = processData("EQP", eqpLogs, true);

  const options = buildFixedHeightOptions(range, 75, {
    minHeight: 28,
    maxHeight: 75,
    align: "top",
    zoomFriction: 5,
  });

  if (eqpLogs.length === 0) {
    return (
      <TimelineEmptyState title="⚙️ EQP 상태" message="EQP 로그가 없습니다" />
    );
  }

  return (
    <BaseTimeline
      groups={[EQP_GROUP]}
      items={items}
      options={options}
      title="⚙️ EQP 상태"
      showTimeAxis={showTimeAxis}
      headerExtra={
        showLegend ? <TimelineLegend items={timelineLegends.EQP} /> : null
      }
    />
  );
}
