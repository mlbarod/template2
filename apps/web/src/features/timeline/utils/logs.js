/**
 * 타임라인 로그 가공에 공통으로 사용하는 작은 유틸리티입니다.
 */
export function addDurationToLogs(logs = [], logType) {
  if (!logs.length) return logs;

  const sortedLogs = [...logs].sort(
    (a, b) => new Date(a.eventTime) - new Date(b.eventTime)
  );

  return sortedLogs.map((log, index) => {
    let duration = null;
    const isRangeType = logType === "EQP" || logType === "TIP";

    if (isRangeType) {
      const startTime = new Date(log.eventTime).getTime();

      if (index < sortedLogs.length - 1) {
        const nextTime = new Date(sortedLogs[index + 1].eventTime).getTime();
        duration = nextTime - startTime;
      } else {
        const now = new Date();
        const todayMidnight = new Date(
          now.getFullYear(),
          now.getMonth(),
          now.getDate(),
          0,
          0,
          0,
          0
        ).getTime();
        duration = todayMidnight - startTime;
      }
    }

    return { ...log, duration };
  });
}

export function mergeLogsByTime(logsByType = {}) {
  const {
    eqpLogs = [],
    tipLogs = [],
    ctttmLogs = [],
    racbLogs = [],
    droneLogs = [],
  } = logsByType;

  return [
    ...eqpLogs,
    ...tipLogs,
    ...ctttmLogs,
    ...racbLogs,
    ...droneLogs,
  ]
    .filter((log) => log && log.eventTime)
    .sort(
      (a, b) =>
        new Date(b.eventTime).getTime() - new Date(a.eventTime).getTime()
    );
}
