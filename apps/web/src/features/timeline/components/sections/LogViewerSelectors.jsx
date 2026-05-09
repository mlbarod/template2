import React from "react";
import EqpSelector from "../EqpSelector";
import LineSelector from "../LineSelector";
import PrcGroupSelector from "../PrcGroupSelector";
import SDWTSelector from "../SDWTSelector";

export default function LogViewerSelectors({
  lineId,
  sdwtId,
  prcGroup,
  eqpId,
  setLine,
  setSdwt,
  setPrcGroup,
  setEqp,
  isDirectQuery,
  directQueryControl,
}) {
  return (
    <div
      className={`grid gap-2 ${
        isDirectQuery ? "grid-cols-[0.8fr_1fr_1fr_1.2fr]" : "grid-cols-4"
      }`}
    >
      <div className={`relative ${isDirectQuery ? "opacity-50" : ""}`}>
        <LineSelector
          lineId={lineId}
          setLineId={isDirectQuery ? () => {} : setLine}
        />
        {isDirectQuery && <div className="absolute inset-0 cursor-not-allowed" />}
      </div>

      <div className={`relative ${isDirectQuery ? "opacity-50" : ""}`}>
        <SDWTSelector
          lineId={lineId}
          sdwtId={sdwtId}
          setSdwtId={isDirectQuery ? () => {} : setSdwt}
        />
        {isDirectQuery && <div className="absolute inset-0 cursor-not-allowed" />}
      </div>

      <div className={`relative ${isDirectQuery ? "opacity-50" : ""}`}>
        <PrcGroupSelector
          lineId={lineId}
          sdwtId={sdwtId}
          prcGroup={prcGroup}
          setPrcGroup={isDirectQuery ? () => {} : setPrcGroup}
        />
        {isDirectQuery && <div className="absolute inset-0 cursor-not-allowed" />}
      </div>

      {isDirectQuery ? (
        directQueryControl
      ) : (
        <EqpSelector
          lineId={lineId}
          sdwtId={sdwtId}
          prcGroup={prcGroup}
          eqpId={eqpId}
          setEqpId={setEqp}
        />
      )}
    </div>
  );
}
