// src/features/timeline/components/CtttmTimeline.jsx
import React from "react";
import BaseTimeline from "./BaseTimeline";
import TimelineLegend from "./TimelineLegend";
import TimelineEmptyState from "./TimelineEmptyState";
import { buildFixedHeightOptions } from "../utils/timelineUtils";
import { processData } from "../utils/visTimelineItems";
import { makeGroupLabel } from "../utils/groupLabel";
import { timelineLegends } from "../utils/timelineLegends";

const CTTTM_GROUP = {
  id: "CTTTM",
  content: makeGroupLabel("CTTTM", "CTTTM"),
  className: "custom-group-label",
  order: 1,
};

export default function CtttmTimeline({
  range,
  showLegend,
  showTimeAxis = false,
  ctttmLogs = [],
}) {
  const items = processData("CTTTM", ctttmLogs);

  const options = buildFixedHeightOptions(range, 76);

  if (ctttmLogs.length === 0) {
    return (
      <TimelineEmptyState
        title="⚠️ CTTTM"
        message="CTTTM 로그가 없습니다"
        bodyClassName="h-[74px]"
      />
    );
  }

  return (
    <BaseTimeline
      groups={[CTTTM_GROUP]}
      items={items}
      options={options}
      title="⚠️ CTTTM"
      showTimeAxis={showTimeAxis}
      headerExtra={
        showLegend ? <TimelineLegend items={timelineLegends.CTTTM} /> : null
      }
    />
  );
}
