// src/features/timeline/components/LogViewerSection.jsx - 개선된 버전
import React from "react";
import DirectEqpQuery from "./sections/DirectEqpQuery";
import LogViewerSelectors from "./sections/LogViewerSelectors";
import { useDirectEquipmentQuery } from "../hooks/useDirectEquipmentQuery";

export default function LogViewerSection({
  lineId,
  sdwtId,
  prcGroup,
  eqpId,
  setLine,
  setSdwt,
  setPrcGroup,
  setEqp,
}) {
  const directQuery = useDirectEquipmentQuery({
    setLine,
    setSdwt,
    setPrcGroup,
    setEqp,
  });

  return (
    <section className="border border-border bg-card shadow-sm rounded-xl p-3 flex flex-col">
      <div className="flex items-center justify-between mb-2">
        <h2 className="text-md font-bold text-foreground">
          📊 Log Viewer
        </h2>
        <label className="flex items-center gap-2 text-xs cursor-pointer">
          <span className="text-muted-foreground">EQPID 바로조회</span>
          <input
            type="checkbox"
            checked={directQuery.isDirectQuery}
            onChange={(e) => directQuery.handleToggleChange(e.target.checked)}
            className="h-4 w-4 rounded text-primary focus:ring-primary"
          />
        </label>
      </div>

      <LogViewerSelectors
        lineId={lineId}
        sdwtId={sdwtId}
        prcGroup={prcGroup}
        eqpId={eqpId}
        setLine={setLine}
        setSdwt={setSdwt}
        setPrcGroup={setPrcGroup}
        setEqp={setEqp}
        isDirectQuery={directQuery.isDirectQuery}
        directQueryControl={
          <DirectEqpQuery
            inputEqpId={directQuery.inputEqpId}
            isLoading={directQuery.isLoading}
            onInputChange={directQuery.handleInputChange}
            onKeyPress={directQuery.handleKeyPress}
            onSubmit={directQuery.handleDirectQuery}
          />
        }
      />
    </section>
  );
}
