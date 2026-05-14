import React from "react";
import { useParams } from "react-router-dom";
import { AdjustmentsHorizontalIcon } from "@heroicons/react/24/outline";
import { LoadingSpinner } from "../components/Loaders";
import TimelineBoard from "../components/TimelineBoard";
import DataLogSection from "../components/DataLogSection";
import LogViewerSection from "../components/LogViewerSection";
import ShareButton from "../components/ShareButton";
import LogDetailSection from "../components/LogDetailSection";
import TimelineSettings from "../components/TimelineSettings";
import { useTimelinePageState } from "../hooks/useTimelinePageState";

export default function TimelinePage() {
  const params = useParams();
  const {
    selection,
    timelinePrefs,
    filters,
    settings,
    validation,
    logs,
    selectedLog,
    timelineReady,
  } = useTimelinePageState(params); // 복잡한 상태를 한 곳에서 준비해 UI 단을 단순화

  const {
    lineId,
    sdwtId,
    prcGroup,
    eqpId,
    setLine,
    setSdwt,
    setPrcGroup,
    setEqp,
  } = selection;

  const {
    showLegend,
    selectedTipGroups,
    setShowLegend,
    setSelectedTipGroups,
  } = timelinePrefs;

  const { typeFilters, handleFilterChange } = filters;
  const { isSettingsOpen, setIsSettingsOpen } = settings;

  const { isValidating, validationError } = validation;
  const { logsLoading, logsWithDuration, tableData, filteredTipLogs } = logs;

  // 검증 중일 때 로딩 표시
  if (isValidating) {
    return (
      <div className="flex items-center justify-center h-[80vh]">
        <LoadingSpinner />
      </div>
    );
  }

  // 검증 에러 표시
  if (validationError) {
    return (
      <div className="flex items-center justify-center h-[80vh]">
        <div className="text-center">
          <p className="text-red-500 mb-2">{validationError}</p>
          <p className="text-muted-foreground">
            잠시 후 메인 페이지로 이동합니다...
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="grid h-full min-h-0 gap-3 overflow-hidden lg:grid-cols-[2fr_3fr]">
      <div className="grid min-h-0 grid-rows-[auto_1fr] gap-2">
        <LogViewerSection
          lineId={lineId}
          sdwtId={sdwtId}
          prcGroup={prcGroup}
          eqpId={eqpId}
          setLine={setLine}
          setSdwt={setSdwt}
          setPrcGroup={setPrcGroup}
          setEqp={setEqp}
        />

        <div className="grid min-h-0 grid-rows-[auto_1fr] gap-2">
          <DataLogSection
            eqpId={eqpId}
            logsLoading={logsLoading}
            tableData={tableData}
            typeFilters={typeFilters}
            handleFilter={handleFilterChange}
          />

          <section className="grid min-h-0 grid-rows-[auto_1fr] gap-2 rounded-xl border border-border bg-card p-3 shadow-sm">
            <div className="flex items-center justify-between">
              <h2 className="text-md font-bold text-foreground">📝 Log Detail</h2>
            </div>
            <div className="min-h-0 overflow-y-auto">
              <LogDetailSection log={selectedLog} />
            </div>
          </section>
        </div>
      </div>

      <div className="grid min-h-0 grid-rows-[auto_1fr] gap-3">
        <div className="flex items-center justify-between rounded-xl border bg-card px-4 py-3 shadow-sm">
          <div className="flex items-center gap-2">
            <h2 className="text-md font-bold text-foreground">📊 Timeline</h2>
            {lineId && eqpId && <ShareButton />}
          </div>

          {eqpId && !logsLoading ? (
            <button
              onClick={() => setIsSettingsOpen(!isSettingsOpen)}
              className="inline-flex items-center gap-1.5 rounded-md border border-border bg-card px-3 py-1.5 text-xs font-medium text-foreground transition hover:bg-muted focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary"
            >
              <AdjustmentsHorizontalIcon className="h-4 w-4" />
              설정
            </button>
          ) : null}
        </div>

        <div className="grid min-h-0 grid-cols-1 gap-2 lg:grid-cols-[1fr_auto]">
          <div className="relative min-h-0 overflow-hidden rounded-xl border bg-card shadow-sm">
            {!eqpId && !logsLoading ? (
              <div className="flex h-full items-center justify-center px-6 text-center text-muted-foreground">
                EQP를 선택하세요.
              </div>
            ) : logsLoading ? (
              <div className="flex h-full items-center justify-center">
                <LoadingSpinner />
              </div>
            ) : (
              <TimelineBoard
                showLegend={showLegend}
                selectedTipGroups={selectedTipGroups}
                eqpLogs={logsWithDuration.eqpLogs}
                tipLogs={logsWithDuration.tipLogs}
                ctttmLogs={logsWithDuration.ctttmLogs}
                racbLogs={logsWithDuration.racbLogs}
                droneLogs={logsWithDuration.droneLogs}
                typeFilters={typeFilters}
              />
            )}
          </div>

          {timelineReady && !logsLoading ? (
            <TimelineSettings
              isOpen={isSettingsOpen}
              onClose={() => setIsSettingsOpen(false)}
              showLegend={showLegend}
              selectedTipGroups={selectedTipGroups}
              onLegendToggle={(e) => setShowLegend(e.target.checked)} // 수정
              onTipFilterChange={setSelectedTipGroups}
              tipLogs={filteredTipLogs}
            />
          ) : null}
        </div>
      </div>
    </div>
  );
}
