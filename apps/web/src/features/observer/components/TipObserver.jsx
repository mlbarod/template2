// src/features/observer/components/TipObserver.jsx
import React from "react";
import BaseObserver from "./BaseObserver";
import ObserverLegend from "./ObserverLegend";
import ObserverEmptyState from "./ObserverEmptyState";
import { buildFixedHeightOptions } from "../utils/observerUtils";
import {
  buildTipObserverData,
  getTipObserverHeight,
} from "../utils/tipObserverGroups";
import { observerLegends } from "../utils/observerLegends";

export default function TipObserver({
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

  const { groups, items } = buildTipObserverData(tipLogs);
  const calculatedHeight = getTipObserverHeight(groups);

  const options = buildFixedHeightOptions(range, calculatedHeight, {
    groupHeightMode: "fixed",
  });

  if (!hasAnyTipLogs || !hasVisibleTipLogs) {
    return (
      <ObserverEmptyState
        title="🔧 TIP 로그"
        message={!hasAnyTipLogs ? "TIP 로그가 없습니다" : "표시할 TIP 그룹을 선택하세요"}
      />
    );
  }

  return (
    <BaseObserver
      key={`tip-observer-${groups.length}`}
      groups={groups}
      items={items}
      options={options}
      title={`🔧 TIP 로그 (${groups.length}개 그룹)`}
      showTimeAxis={showTimeAxis}
      className="tip-observer"
      headerExtra={
        showLegend ? <ObserverLegend items={observerLegends.TIP} /> : null
      }
    />
  );
}
