import React from "react";
import BaseObserver from "./BaseObserver";
import ObserverLegend from "./ObserverLegend";
import ObserverEmptyState from "./ObserverEmptyState";
import { buildFixedHeightOptions } from "../utils/observerUtils";
import { processData } from "../utils/visObserverItems";
import { makeGroupLabel } from "../utils/groupLabel";
import { getEsopChangeTypeLegendsForLogs } from "../utils/esopChangeTypes";

const ESOP_GROUP = {
  id: "ESOP",
  content: makeGroupLabel("ESOP", "ESOP"),
  className: "custom-group-label",
  order: 1,
};

export default function EsopObserver({
  range,
  showLegend,
  showTimeAxis = false,
  esopLogs = [],
}) {
  const items = processData("ESOP", esopLogs);
  const legendItems = getEsopChangeTypeLegendsForLogs(esopLogs);

  const options = buildFixedHeightOptions(range, 76);

  if (esopLogs.length === 0) {
    return (
      <ObserverEmptyState title="🚁 ESOP" message="ESOP 로그가 없습니다" />
    );
  }

  return (
    <BaseObserver
      groups={[ESOP_GROUP]}
      items={items}
      options={options}
      title="🚁 ESOP"
      showTimeAxis={showTimeAxis}
      headerExtra={
        showLegend ? <ObserverLegend items={legendItems} /> : null
      }
    />
  );
}
