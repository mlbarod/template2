import { ESOP_CHANGE_TYPE_CLASS_MAP } from "./esopChangeTypes";
import { OBSERVER_COLOR_CLASSES } from "./observerColorClasses";

/**
 * 각 로그 타입(logType)별 컬러 매핑.
 * 클래스 이름은 observer.css의 Radix scale 클래스로 연결됩니다.
 */
export const groupConfig = {
  EQP: {
    stateClasses: {
      RUN: OBSERVER_COLOR_CLASSES.EQP_RUN,
      DOWN: OBSERVER_COLOR_CLASSES.EQP_DOWN,
      PM: OBSERVER_COLOR_CLASSES.EQP_PM,
      IDLE: OBSERVER_COLOR_CLASSES.EQP_IDLE,
      LOCAL: OBSERVER_COLOR_CLASSES.EQP_LOCAL,
    },
  },
  TIP: {
    stateClasses: {
      L1_CNT: OBSERVER_COLOR_CLASSES.TIP_OPEN,
      L2_CNT: OBSERVER_COLOR_CLASSES.TIP_OPEN,
      L3_CNT: OBSERVER_COLOR_CLASSES.TIP_OPEN,
      DOING: OBSERVER_COLOR_CLASSES.TIP_OPEN,

      L1_TIP: OBSERVER_COLOR_CLASSES.TIP_CLOSE,
      L2_TIP: OBSERVER_COLOR_CLASSES.TIP_CLOSE,
      L3_TIP: OBSERVER_COLOR_CLASSES.TIP_CLOSE,
    },
  },
  RACB: {
    defaultClass: OBSERVER_COLOR_CLASSES.RACB,
  },
  CTTTM: {
    stateClasses: {
      CBM: OBSERVER_COLOR_CLASSES.CTTTM_CBM,
      NSP: OBSERVER_COLOR_CLASSES.CTTTM_NSP,
    },
  },
  ESOP: {
    defaultClass: OBSERVER_COLOR_CLASSES.ESOP_DEFAULT,
    stateClasses: ESOP_CHANGE_TYPE_CLASS_MAP,
  },
};
