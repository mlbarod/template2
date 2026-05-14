import React from "react";
import BaseTimeline from "./BaseTimeline";
import TimelineLegend from "./TimelineLegend";
import TimelineEmptyState from "./TimelineEmptyState";
import { buildFixedHeightOptions } from "../utils/timelineUtils";
import { processData } from "../utils/visTimelineItems";
import { makeGroupLabel } from "../utils/groupLabel";
import { timelineLegends } from "../utils/timelineLegends";

const DRONE_GROUP = {
  id: "DRONE",
  content: makeGroupLabel("DRONE", "DRONE"),
  className: "custom-group-label",
  order: 1,
};

export default function DroneTimeline({
  range,
  showLegend,
  showTimeAxis = false,
  droneLogs = [],
}) {
  const items = processData("DRONE", droneLogs);

  const options = buildFixedHeightOptions(range, 76);

  if (droneLogs.length === 0) {
    return (
      <TimelineEmptyState title="🚁 DRONE" message="DRONE 로그가 없습니다" />
    );
  }

  return (
    <BaseTimeline
      groups={[DRONE_GROUP]}
      items={items}
      options={options}
      title="🚁 DRONE"
      showTimeAxis={showTimeAxis}
      headerExtra={
        showLegend ? <TimelineLegend items={timelineLegends.DRONE} /> : null
      }
    />
  );
}
