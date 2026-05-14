import React from "react";
import EqpTimeline from "./EqpTimeline";
import TipTimeline from "./TipTimeline";
import CtttmTimeline from "./CtttmTimeline";
import RacbTimeline from "./RacbTimeline";
import DroneTimeline from "./DroneTimeline";
import { useTimelineRange } from "../hooks/useTimelineRange";
import { filterTipLogsByGroups } from "../utils/tipUtils";

export default function TimelineBoard({
  showLegend,
  selectedTipGroups,
  eqpLogs = [],
  tipLogs = [],
  ctttmLogs = [],
  racbLogs = [],
  droneLogs = [],
  typeFilters,
}) {
  const visibleTipLogs = filterTipLogsByGroups(tipLogs, selectedTipGroups);

  const visibleLogs = [
    ...(typeFilters?.EQP ? eqpLogs : []),
    ...(typeFilters?.TIP ? visibleTipLogs : []),
    ...(typeFilters?.CTTTM ? ctttmLogs : []),
    ...(typeFilters?.RACB ? racbLogs : []),
    ...(typeFilters?.DRONE ? droneLogs : []),
  ];

  const range = useTimelineRange(visibleLogs);
  const hasVisibleLogs = visibleLogs.length > 0;

  // 아무 데이터도 없는 경우
  if (!hasVisibleLogs) {
    return (
      <div className="flex items-center justify-center h-64 text-muted-foreground">
        표시할 로그 데이터가 없습니다. 필터를 확인해주세요.
      </div>
    );
  }

  return (
    <div className="w-full h-full relative">
      {/* 타임라인이 많아질 때를 위한 스크롤 컨테이너 - absolute로 부모의 전체 영역을 차지 */}
      <div className="absolute inset-0 overflow-y-auto space-y-0 scroll-smooth px-3 mt-5 mb-10 z-[1]">
        {/* EQP 타임라인 */}
        {typeFilters?.EQP && (
          <EqpTimeline
            range={range}
            showLegend={showLegend}
            showTimeAxis={true}
            eqpLogs={eqpLogs}
          />
        )}

        {/* TIP 타임라인 */}
        {typeFilters?.TIP && (
          <TipTimeline
            range={range}
            showLegend={showLegend}
            showTimeAxis={true}
            totalTipLogCount={tipLogs.length}
            tipLogs={visibleTipLogs}
          />
        )}

        {/* CTTTM 타임라인 */}
        {typeFilters?.CTTTM && (
          <CtttmTimeline
            range={range}
            showLegend={showLegend}
            showTimeAxis={true}
            ctttmLogs={ctttmLogs}
          />
        )}

        {/* RACB 타임라인 */}
        {typeFilters?.RACB && (
          <RacbTimeline
            range={range}
            showLegend={showLegend}
            showTimeAxis={true}
            racbLogs={racbLogs}
          />
        )}

        {/* DRONE 타임라인 */}
        {typeFilters?.DRONE && (
          <DroneTimeline
            range={range}
            showLegend={showLegend}
            showTimeAxis={true}
            droneLogs={droneLogs}
          />
        )}
      </div>
    </div>
  );
}
