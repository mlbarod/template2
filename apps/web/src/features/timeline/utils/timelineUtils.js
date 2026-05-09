// src/features/timeline/utils/timelineUtils.js
// timeline 범위와 옵션 계산 유틸만 제공합니다.

/** 전체 로그 범위 계산 */
export const calcRange = (logs) => {
  if (!logs || logs.length === 0) {
    // 로그가 없을 때 기본값
    const now = new Date();
    return {
      min: new Date(now.getFullYear(), now.getMonth(), now.getDate()),
      max: new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1),
    };
  }

  // eventTime이 있는 로그만 필터링
  const validLogs = logs.filter((log) => log && log.eventTime);

  if (validLogs.length === 0) {
    const now = new Date();
    return {
      min: new Date(now.getFullYear(), now.getMonth(), now.getDate()),
      max: new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1),
    };
  }

  // 모든 시간을 추출 (eventTime과 endTime 모두 고려)
  const allTimes = [];

  validLogs.forEach((log) => {
    const eventTime = new Date(log.eventTime).getTime();
    if (!isNaN(eventTime)) {
      allTimes.push(eventTime);
    }

    // endTime도 있다면 포함
    if (log.endTime) {
      const endTime = new Date(log.endTime).getTime();
      if (!isNaN(endTime)) {
        allTimes.push(endTime);
      }
    }
  });

  if (allTimes.length === 0) {
    const now = new Date();
    return {
      min: new Date(now.getFullYear(), now.getMonth(), now.getDate()),
      max: new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1),
    };
  }

  const minTime = Math.min(...allTimes);
  const maxTime = Math.max(...allTimes);

  return {
    min: new Date(minTime),
    max: new Date(maxTime),
  };
};

const getEndOfToday = () => {
  const now = new Date();
  return new Date(now.getFullYear(), now.getMonth(), now.getDate(), 23, 59, 59, 999);
};

/** 버퍼 추가 (줌 아웃 시 오늘까지는 항상 포함) */
export const addBuffer = (min, max) => {
  const todayEnd = getEndOfToday().getTime();
  const effectiveMax = Math.max(max, todayEnd);
  const range = effectiveMax - min;
  const bufferRatio = 0.1; // 전체 범위의 10%를 버퍼로
  const buffer = Math.max(range * bufferRatio, 24 * 60 * 60 * 1000); // 최소 1일

  return {
    min: new Date(min - buffer),
    max: new Date(effectiveMax + buffer),
  };
};

const ONE_HOUR_MS = 60 * 60 * 1000;

export const buildFixedHeightOptions = (range, height, overrides = {}) => {
  const { minHeight, maxHeight, ...rest } = overrides;

  return {
    stack: false,
    min: range.min,
    max: range.max,
    zoomMin: ONE_HOUR_MS,
    height,
    minHeight: minHeight ?? height,
    maxHeight: maxHeight ?? height,
    verticalScroll: false,
    horizontalScroll: false,
    ...rest,
  };
};
