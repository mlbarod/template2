import { ESOP_CHANGE_TYPE_CLASS_MAP } from "./esopChangeTypes";

/**
 * 각 로그 타입(logType)별 컬러 매핑.
 * 클래스 이름은 observer.css에서 디자인 토큰 기반 색상으로 연결됩니다.
 */
export const groupConfig = {
  EQP: {
    stateClasses: {
      RUN: "observer-color-eqp-run",
      DOWN: "observer-color-eqp-down",
      PM: "observer-color-eqp-pm",
      IDLE: "observer-color-eqp-idle",
      LOCAL: "observer-color-eqp-local",
    },
  },
  TIP: {
    stateClasses: {
      L1_CNT: "observer-color-tip-open",
      L2_CNT: "observer-color-tip-open",
      L3_CNT: "observer-color-tip-open",
      DOING: "observer-color-tip-open",

      L1_TIP: "observer-color-tip-close",
    },
  },
  RACB: {
    stateClasses: {
      ALARM: "observer-color-racb-alarm",
      WARN: "observer-color-racb-warn",
    },
  },
  CTTTM: {
    stateClasses: {
      CBM: "observer-color-ctttm-cbm",
      NSP: "observer-color-ctttm-nsp",
    },
  },
  ESOP: {
    defaultClass: "observer-color-esop",
    stateClasses: ESOP_CHANGE_TYPE_CLASS_MAP,
  },
};
