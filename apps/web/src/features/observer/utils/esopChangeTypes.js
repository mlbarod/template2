import { OBSERVER_COLOR_CLASSES } from "./observerColorClasses";

export const ESOP_CHANGE_TYPE_LEGENDS = [
  {
    key: "ENGR_FOUP_SPLIT_STEP",
    className: OBSERVER_COLOR_CLASSES.ESOP_FOUP_SPLIT_STEP,
    label: "ENGR_FOUP_SPLIT_STEP",
  },
  {
    key: "ENGR_PRODUCTION",
    className: OBSERVER_COLOR_CLASSES.ESOP_PRODUCTION,
    label: "ENGR_PRODUCTION",
  },
  {
    key: "ENGR_FOUP_SPLIT",
    className: OBSERVER_COLOR_CLASSES.ESOP_FOUP_SPLIT,
    label: "ENGR_FOUP_SPLIT",
  },
  {
    key: "ENGR_PRODUCTION_ANY",
    className: OBSERVER_COLOR_CLASSES.ESOP_PRODUCTION_ANY,
    label: "ENGR_PRODUCTION_ANY",
  },
  {
    key: "ENGR_LOGICAL_SPLIT",
    className: OBSERVER_COLOR_CLASSES.ESOP_LOGICAL_SPLIT,
    label: "ENGR_LOGICAL_SPLIT",
  },
  {
    key: "ENGR_FOUP_SPLIT_STEP_SKEW",
    className: OBSERVER_COLOR_CLASSES.ESOP_FOUP_SPLIT_STEP_SKEW,
    label: "ENGR_FOUP_SPLIT_STEP_SKEW",
  },
  {
    key: "ENGR_FOUP_SPLIT_STEP_ANY",
    className: OBSERVER_COLOR_CLASSES.ESOP_FOUP_SPLIT_STEP_ANY,
    label: "ENGR_FOUP_SPLIT_STEP_ANY",
  },
  {
    key: "ENGR_FOUP_SPLIT_SKEW",
    className: OBSERVER_COLOR_CLASSES.ESOP_FOUP_SPLIT_SKEW,
    label: "ENGR_FOUP_SPLIT_SKEW",
  },
  {
    key: "ENGR_FOUP_SPLIT_STEP_RISK",
    className: OBSERVER_COLOR_CLASSES.ESOP_FOUP_SPLIT_STEP_RISK,
    label: "ENGR_FOUP_SPLIT_STEP_RISK",
  },
  {
    key: "ENGR_BATCH_SKEW",
    className: OBSERVER_COLOR_CLASSES.ESOP_BATCH_SKEW,
    label: "ENGR_BATCH_SKEW",
  },
  {
    key: "ENGR_FOUP_SPLIT_ANY",
    className: OBSERVER_COLOR_CLASSES.ESOP_FOUP_SPLIT_ANY,
    label: "ENGR_FOUP_SPLIT_ANY",
  },
  {
    key: "ENGR_LOGICAL_SPLIT_SKEW",
    className: OBSERVER_COLOR_CLASSES.ESOP_LOGICAL_SPLIT_SKEW,
    label: "ENGR_LOGICAL_SPLIT_SKEW",
  },
  {
    key: "ENGR_FOUP_SPLIT_STEP_SKEW_ANY",
    className: OBSERVER_COLOR_CLASSES.ESOP_FOUP_SPLIT_STEP_SKEW_ANY,
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
      OBSERVER_COLOR_CLASSES.ESOP_FOUP_SPLIT_STEP_SKEW_ANY,
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
        className: OBSERVER_COLOR_CLASSES.ESOP_DEFAULT,
        label: eventType,
      })),
  ];
}
