export const ESOP_CHANGE_TYPE_LEGENDS = [
  {
    key: "ENGR_FOUP_SPLIT_STEP",
    className: "observer-color-esop-foup-split-step",
    label: "ENGR_FOUP_SPLIT_STEP",
  },
  {
    key: "ENGR_PRODUCTION",
    className: "observer-color-esop-production",
    label: "ENGR_PRODUCTION",
  },
  {
    key: "ENGR_FOUP_SPLIT",
    className: "observer-color-esop-foup-split",
    label: "ENGR_FOUP_SPLIT",
  },
  {
    key: "ENGR_PRODUCTION_ANY",
    className: "observer-color-esop-production-any",
    label: "ENGR_PRODUCTION_ANY",
  },
  {
    key: "ENGR_LOGICAL_SPLIT",
    className: "observer-color-esop-logical-split",
    label: "ENGR_LOGICAL_SPLIT",
  },
  {
    key: "ENGR_FOUP_SPLIT_STEP_SKEW",
    className: "observer-color-esop-foup-split-step-skew",
    label: "ENGR_FOUP_SPLIT_STEP_SKEW",
  },
  {
    key: "ENGR_FOUP_SPLIT_STEP_ANY",
    className: "observer-color-esop-foup-split-step-any",
    label: "ENGR_FOUP_SPLIT_STEP_ANY",
  },
  {
    key: "ENGR_FOUP_SPLIT_SKEW",
    className: "observer-color-esop-foup-split-skew",
    label: "ENGR_FOUP_SPLIT_SKEW",
  },
  {
    key: "ENGR_FOUP_SPLIT_STEP_RISK",
    className: "observer-color-esop-foup-split-step-risk",
    label: "ENGR_FOUP_SPLIT_STEP_RISK",
  },
  {
    key: "ENGR_BATCH_SKEW",
    className: "observer-color-esop-batch-skew",
    label: "ENGR_BATCH_SKEW",
  },
  {
    key: "ENGR_FOUP_SPLIT_ANY",
    className: "observer-color-esop-foup-split-any",
    label: "ENGR_FOUP_SPLIT_ANY",
  },
  {
    key: "ENGR_LOGICAL_SPLIT_SKEW",
    className: "observer-color-esop-logical-split-skew",
    label: "ENGR_LOGICAL_SPLIT_SKEW",
  },
  {
    key: "ENGR_FOUP_SPLIT_STEP_SKEW_ANY",
    className: "observer-color-esop-foup-split-step-skew-any",
    label: "ENGR_FOUP_SPLIT_STEP_SKEW_ANY",
  },
];

export const ESOP_CHANGE_TYPE_CLASS_MAP = ESOP_CHANGE_TYPE_LEGENDS.reduce(
  (acc, item) => ({
    ...acc,
    [item.key]: item.className,
  }),
  {
    ENGR_FOUP_SPLIT_STEP_SKEw_ANY:
      "observer-color-esop-foup-split-step-skew-any",
  }
);

const ESOP_CHANGE_TYPE_DISPLAY_KEY_MAP = {
  ENGR_FOUP_SPLIT_STEP_SKEw_ANY: "ENGR_FOUP_SPLIT_STEP_SKEW_ANY",
};

export function getEsopChangeTypeLegendsForLogs(logs = []) {
  const presentEventTypes = new Set(
    logs
      .map((log) => log?.eventType)
      .filter(Boolean)
  );
  const presentLegendKeys = new Set(
    Array.from(presentEventTypes, (eventType) =>
      ESOP_CHANGE_TYPE_DISPLAY_KEY_MAP[eventType] ?? eventType
    )
  );
  const knownLegendKeys = new Set(ESOP_CHANGE_TYPE_LEGENDS.map((item) => item.key));

  return [
    ...ESOP_CHANGE_TYPE_LEGENDS.filter((item) => presentLegendKeys.has(item.key)),
    ...Array.from(presentEventTypes)
      .filter((eventType) => {
        const legendKey = ESOP_CHANGE_TYPE_DISPLAY_KEY_MAP[eventType] ?? eventType;
        return !knownLegendKeys.has(legendKey);
      })
      .map((eventType) => ({
        key: eventType,
        className: "observer-color-esop",
        label: eventType,
      })),
  ];
}
