import { useQuery } from "@tanstack/react-query";
import { observerApi } from "../api/observerApi";

const TKIN_PREVENT_KEY = ["observer", "tkinPrevent"];

export const useTkinPreventProcesses = (lineId, sdwtId, prcGroup) =>
  useQuery({
    queryKey: [...TKIN_PREVENT_KEY, "processes", lineId, sdwtId, prcGroup],
    queryFn: () =>
      observerApi.fetchTkinPreventProcesses({ lineId, sdwtId, prcGroup }),
    enabled: !!lineId && !!sdwtId && !!prcGroup,
    staleTime: 1000 * 60 * 10,
  });

export const useTkinPreventStepSeqs = (
  lineId,
  sdwtId,
  prcGroup,
  processId
) =>
  useQuery({
    queryKey: [
      ...TKIN_PREVENT_KEY,
      "stepSeqs",
      lineId,
      sdwtId,
      prcGroup,
      processId,
    ],
    queryFn: () =>
      observerApi.fetchTkinPreventStepSeqs({
        lineId,
        sdwtId,
        prcGroup,
        processId,
      }),
    enabled: !!lineId && !!sdwtId && !!prcGroup && !!processId,
    staleTime: 1000 * 60 * 10,
  });

export const useTkinPreventMatrix = (
  lineId,
  sdwtId,
  prcGroup,
  processId,
  stepSeq
) =>
  useQuery({
    queryKey: [
      ...TKIN_PREVENT_KEY,
      "matrix",
      lineId,
      sdwtId,
      prcGroup,
      processId,
      stepSeq,
    ],
    queryFn: () =>
      observerApi.fetchTkinPreventMatrix({
        lineId,
        sdwtId,
        prcGroup,
        processId,
        stepSeq,
      }),
    enabled: !!lineId && !!sdwtId && !!prcGroup && !!processId && !!stepSeq,
    staleTime: 1000 * 60 * 5,
  });
