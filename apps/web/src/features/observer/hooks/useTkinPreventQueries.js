import { useQuery } from "@tanstack/react-query";
import { observerApi } from "../api/observerApi";

const TKIN_PREVENT_KEY = ["observer", "tkinPrevent"];

export const useTkinPreventPrcGroups = (userSdwtProd) =>
  useQuery({
    queryKey: [...TKIN_PREVENT_KEY, "prcGroups", userSdwtProd],
    queryFn: () => observerApi.fetchTkinPreventPrcGroups({ userSdwtProd }),
    enabled: !!userSdwtProd,
    staleTime: 1000 * 60 * 10,
  });

export const useTkinPreventProcesses = (userSdwtProd, prcGroup) =>
  useQuery({
    queryKey: [...TKIN_PREVENT_KEY, "processes", userSdwtProd, prcGroup],
    queryFn: () =>
      observerApi.fetchTkinPreventProcesses({ userSdwtProd, prcGroup }),
    enabled: !!userSdwtProd && !!prcGroup,
    staleTime: 1000 * 60 * 10,
  });

export const useTkinPreventStepSeqs = (
  userSdwtProd,
  prcGroup,
  processId
) =>
  useQuery({
    queryKey: [
      ...TKIN_PREVENT_KEY,
      "stepSeqs",
      userSdwtProd,
      prcGroup,
      processId,
    ],
    queryFn: () =>
      observerApi.fetchTkinPreventStepSeqs({
        userSdwtProd,
        prcGroup,
        processId,
      }),
    enabled: !!userSdwtProd && !!prcGroup && !!processId,
    staleTime: 1000 * 60 * 10,
  });

export const useTkinPreventMatrix = (
  userSdwtProd,
  prcGroup,
  processId,
  stepSeq
) =>
  useQuery({
    queryKey: [
      ...TKIN_PREVENT_KEY,
      "matrix",
      userSdwtProd,
      prcGroup,
      processId,
      stepSeq,
    ],
    queryFn: () =>
      observerApi.fetchTkinPreventMatrix({
        userSdwtProd,
        prcGroup,
        processId,
        stepSeq,
      }),
    enabled: !!userSdwtProd && !!prcGroup && !!processId && !!stepSeq,
    staleTime: 1000 * 60 * 5,
  });
