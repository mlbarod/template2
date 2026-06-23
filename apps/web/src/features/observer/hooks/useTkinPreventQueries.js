import { useQuery } from "@tanstack/react-query";
import { observerApi } from "../api/observerApi";

const TKIN_PREVENT_KEY = ["observer", "tkinPrevent"];

export const useTkinPreventProcesses = (sdwtId, prcGroup) =>
  useQuery({
    queryKey: [...TKIN_PREVENT_KEY, "processes", sdwtId, prcGroup],
    queryFn: () =>
      observerApi.fetchTkinPreventProcesses({ sdwtId, prcGroup }),
    enabled: !!sdwtId && !!prcGroup,
    staleTime: 1000 * 60 * 10,
  });

export const useTkinPreventStepSeqs = (
  sdwtId,
  prcGroup,
  processId
) =>
  useQuery({
    queryKey: [
      ...TKIN_PREVENT_KEY,
      "stepSeqs",
      sdwtId,
      prcGroup,
      processId,
    ],
    queryFn: () =>
      observerApi.fetchTkinPreventStepSeqs({
        sdwtId,
        prcGroup,
        processId,
      }),
    enabled: !!sdwtId && !!prcGroup && !!processId,
    staleTime: 1000 * 60 * 10,
  });

export const useTkinPreventMatrix = (
  sdwtId,
  prcGroup,
  processId,
  stepSeq
) =>
  useQuery({
    queryKey: [
      ...TKIN_PREVENT_KEY,
      "matrix",
      sdwtId,
      prcGroup,
      processId,
      stepSeq,
    ],
    queryFn: () =>
      observerApi.fetchTkinPreventMatrix({
        sdwtId,
        prcGroup,
        processId,
        stepSeq,
      }),
    enabled: !!sdwtId && !!prcGroup && !!processId && !!stepSeq,
    staleTime: 1000 * 60 * 5,
  });
