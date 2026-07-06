import React, { useEffect, useState } from "react";
import { Maximize2 } from "lucide-react";
import { useParams } from "react-router-dom";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { LoadingSpinner } from "../components/Loaders";
import ObserverBoard from "../components/ObserverBoard";
import DataLogSection from "../components/DataLogSection";
import LogViewerSection from "../components/LogViewerSection";
import LogDetailSection from "../components/LogDetailSection";
import ObserverSettings from "../components/ObserverSettings";
import { useObserverPageState } from "../hooks/useObserverPageState";

export default function ObserverPage() {
  const params = useParams();
  const [isLogDetailDialogOpen, setIsLogDetailDialogOpen] = useState(false);
  const {
    selection,
    observerPrefs,
    filters,
    settings,
    validation,
    logs,
    selectedLog,
    observerReady,
  } = useObserverPageState(params); // 복잡한 상태를 한 곳에서 준비해 UI 단을 단순화

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
  } = observerPrefs;

  const { typeFilters, handleFilterChange } = filters;
  const {
    isSettingsOpen,
    setIsSettingsOpen,
    logRange,
    setLogRange,
  } = settings;

  const { isValidating, validationError } = validation;
  const {
    logsLoading,
    logsWithDuration,
    tableData,
    filteredTipLogs,
    logErrors,
    refetchFailedLogs,
  } = logs;
  const isCtttmLogSelected = selectedLog?.logType === "CTTTM";
  const isLogSelected = Boolean(selectedLog);
  const selectedLogType = selectedLog?.logType || "Log";

  useEffect(() => {
    setIsLogDetailDialogOpen(false);
  }, [selectedLog?.id]);

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
    <>
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
          logRange={logRange}
          onLogRangeChange={setLogRange}
          showSettingsButton={true}
          isSettingsOpen={isSettingsOpen}
          isSettingsDisabled={!observerReady || logsLoading}
          onSettingsToggle={() => setIsSettingsOpen(!isSettingsOpen)}
          showShareButton={true}
        />

        <div className="grid min-h-0 grid-rows-[auto_1fr] gap-2">
          <DataLogSection
            eqpId={eqpId}
            logsLoading={logsLoading}
            tableData={tableData}
            typeFilters={typeFilters}
            handleFilter={handleFilterChange}
            logErrors={logErrors}
            onRetryLogs={refetchFailedLogs}
          />

          <section className="grid min-h-0 grid-rows-[auto_1fr] gap-2 rounded-xl border border-border bg-card p-3 shadow-sm">
            <div className="flex min-w-0 items-center justify-between gap-3">
              <h2 className="min-w-0 text-md font-bold text-foreground">📝 Log Detail</h2>
              {isLogSelected && (
                <div className="flex shrink-0 items-center gap-2">
                  {isCtttmLogSelected ? (
                    <div
                      className="flex items-center gap-1.5 rounded-md px-2 py-1 text-[12px] font-bold ring-1 ring-ring/20"
                      aria-label="Powered by Qwen"
                    >
                      <span>Powered by Qwen AI</span>
                      <img
                        src="/icons/qwen-ai-logo.png"
                        alt=""
                        className="size-4 rounded-sm object-cover object-left"
                        aria-hidden="true"
                      />
                    </div>
                  ) : null}
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon-sm"
                    className="size-7"
                    aria-label={`${selectedLogType} Log Detail 최대화`}
                    title="최대화"
                    onClick={() => setIsLogDetailDialogOpen(true)}
                  >
                    <Maximize2 className="size-4" />
                  </Button>
                </div>
              )}
            </div>
            <div className="min-h-0 overflow-y-auto">
              <LogDetailSection log={selectedLog} />
            </div>
          </section>
        </div>
      </div>

      <div className="grid h-full min-h-0 grid-rows-[1fr] gap-3">
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
              <ObserverBoard
                showLegend={showLegend}
                selectedTipGroups={selectedTipGroups}
                eqpLogs={logsWithDuration.eqpLogs}
                tipLogs={logsWithDuration.tipLogs}
                ctttmLogs={logsWithDuration.ctttmLogs}
                racbLogs={logsWithDuration.racbLogs}
                esopLogs={logsWithDuration.esopLogs}
                typeFilters={typeFilters}
              />
            )}
          </div>

          {observerReady && !logsLoading ? (
            <ObserverSettings
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
      <Dialog
        open={isLogSelected && isLogDetailDialogOpen}
        onOpenChange={setIsLogDetailDialogOpen}
      >
        <DialogContent className="grid h-[min(90dvh,900px)] max-h-[90dvh] w-[min(1200px,calc(100vw-2rem))] max-w-[min(1200px,calc(100vw-2rem))] grid-rows-[auto_minmax(0,1fr)] overflow-hidden p-4 sm:max-w-[min(1200px,calc(100vw-2rem))]">
          <DialogHeader className="pr-8">
            <DialogTitle>{selectedLogType} Log Detail</DialogTitle>
            <DialogDescription className="sr-only">
              선택한 {selectedLogType} 로그 상세 정보를 최대화된 모달에서 표시합니다.
            </DialogDescription>
          </DialogHeader>
          <div className="min-h-0 overflow-auto rounded-md border border-border bg-card p-3">
            <LogDetailSection log={selectedLog} textSizeClass="text-sm" />
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
