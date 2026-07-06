import React from "react";
import EqpDetail from "./EqpDetail";
import TipDetail from "./TipDetail";
import RacbDetail from "./RacbDetail";
import CtttmDetail from "./CtttmDetail";
import EsopDetail from "./EsopDetail";

/**
 * 선택된 로그 상세정보를 보여주는 컴포넌트
 * 로그 타입에 따라 적절한 상세 컴포넌트를 렌더링합니다
 * @param {Object} log - 상세를 보여줄 로그 객체
 */
export default function LogDetailSection({
  log,
  className = "",
  overflowClassName = "overflow-auto",
  textSizeClass = "text-xs",
  summaryStreamingScrollClassName,
}) {
  if (!log) {
    return (
      <div className="text-sm text-muted-foreground text-center py-17">
        테이블이나 Observer에서 로그를 선택하면 상세정보가 표시됩니다.
      </div>
    );
  }

  // 로그 타입에 따라 적절한 컴포넌트 렌더링
  const renderDetailComponent = () => {
    switch (log.logType) {
      case "EQP":
        return <EqpDetail log={log} />;
      case "TIP":
        return <TipDetail log={log} />;
      case "RACB":
        return <RacbDetail log={log} />;
      case "CTTTM":
        return (
          <CtttmDetail
            log={log}
            summaryStreamingScrollClassName={summaryStreamingScrollClassName}
          />
        );
      case "ESOP":
        return <EsopDetail log={log} />;
      default:
        return (
          <div className="col-span-4 text-muted-foreground py-2">
            알 수 없는 로그 타입입니다.
          </div>
        );
    }
  };

  return (
    <div
      className={`grid grid-cols-[max-content_minmax(0,1fr)_max-content_minmax(0,1fr)] gap-x-4 gap-y-2 ${textSizeClass}
       rounded-lg p-2
      text-foreground ${overflowClassName} ${className}`}
    >
      {renderDetailComponent()}
    </div>
  );
}
