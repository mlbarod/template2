import { useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import {
  DEFAULT_TYPE_FILTERS,
} from "../utils/constants";
import {
  buildLogDateRangeOptions,
  getDefaultLogRange,
  getLogRangeFromSearchParams,
  normalizeLogRange,
} from "../utils/logDateRange";
import { useObserverSelectionStore } from "../store/useObserverSelectionStore";
import { useObserverStore } from "../store/useObserverStore";
import { useObserverLogs } from "./useObserverLogs";
import { useEquipmentInfoQuery } from "./useEquipmentInfoQuery";

/**
 * ObserverPage에서 흩어져 있던 상태/파생 데이터를 한 곳에 모아둔 훅.
 * - URL 검증 및 동기화
 * - 드릴다운/Observer 전용 전역 상태
 * - 테이블/Observer에 필요한 파생 데이터 계산
 */
export function useObserverPageState(params) {
  const navigate = useNavigate();
  const location = useLocation();
  const {
    lineId,
    sdwtId,
    prcGroup,
    eqpId,
    setLine,
    setSdwt,
    setPrcGroup,
    setEqp,
    selectedRow,
    resetSelection,
  } = useObserverSelectionStore();

  const {
    showLegend,
    selectedTipGroups,
    setShowLegend,
    setSelectedTipGroups,
  } = useObserverStore();

  // 페이지 로컬 UI 상태
  const [typeFilters, setTypeFilters] = useState({ ...DEFAULT_TYPE_FILTERS });
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [logRange, setLogRange] = useState(() => {
    const initialRange = getLogRangeFromSearchParams(
      new URLSearchParams(location.search)
    );
    return initialRange || getDefaultLogRange();
  });
  const logQueryOptions = useMemo(
    () => buildLogDateRangeOptions(logRange),
    [logRange]
  );

  // URL 파라미터 검증 및 상태 반영 (과도한 파일 분리를 줄이기 위해 이 훅 안에서 처리)
  const [validationError, setValidationError] = useState(null);
  const shouldValidateEqpOnly = Boolean(params.eqpId && !params.lineId);
  const {
    data: equipmentInfo,
    isFetching: isEquipmentInfoFetching,
    isError: isEquipmentInfoError,
    error: equipmentInfoError,
  } = useEquipmentInfoQuery(params.eqpId, { enabled: shouldValidateEqpOnly });

  const isValidating = shouldValidateEqpOnly && isEquipmentInfoFetching;
  const hasValidationResult = !shouldValidateEqpOnly || !isEquipmentInfoFetching;

  useEffect(() => {
    const nextRange = getLogRangeFromSearchParams(
      new URLSearchParams(location.search)
    );
    if (!nextRange) return;

    setLogRange((currentRange) => {
      const current = normalizeLogRange(currentRange);
      if (
        current.startDaysAgo === nextRange.startDaysAgo &&
        current.endDaysAgo === nextRange.endDaysAgo
      ) {
        return currentRange;
      }

      return nextRange;
    });
  }, [location.search]);

  useEffect(() => {
    const nextParams = new URLSearchParams(location.search);
    let hasChanged = false;

    for (const [key, value] of Object.entries(logQueryOptions)) {
      if (nextParams.get(key) !== value) {
        nextParams.set(key, value);
        hasChanged = true;
      }
    }

    if (!hasChanged) return;

    navigate(
      {
        pathname: location.pathname,
        search: `?${nextParams.toString()}`,
        hash: location.hash,
      },
      { replace: true }
    );
  }, [
    location.hash,
    location.pathname,
    location.search,
    logQueryOptions,
    navigate,
  ]);

  useEffect(() => {
    if (!shouldValidateEqpOnly) {
      setValidationError(null);
      return;
    }

    if (equipmentInfo) {
      setValidationError(null);
      setLine(equipmentInfo.lineId);
      setSdwt(equipmentInfo.sdwtId);
      setPrcGroup(equipmentInfo.prcGroup);
      setEqp(params.eqpId);
      return;
    }

    if (isEquipmentInfoError || (!equipmentInfo && !isEquipmentInfoFetching)) {
      const message =
        equipmentInfoError instanceof Error
          ? equipmentInfoError.message
          : "유효하지 않은 EQP ID입니다.";
      setValidationError(message);
      const timeoutId = setTimeout(() => navigate("/observer"), 1500);
      return () => clearTimeout(timeoutId);
    }
  }, [
    equipmentInfo,
    equipmentInfoError,
    isEquipmentInfoError,
    isEquipmentInfoFetching,
    navigate,
    params.eqpId,
    setEqp,
    setLine,
    setPrcGroup,
    setSdwt,
    shouldValidateEqpOnly,
  ]);

  // 선택한 eqpId와 URL을 동기화
  useEffect(() => {
    if (isValidating || !hasValidationResult) return;

    const currentPath = location.pathname;
    const isParamRoute =
      currentPath.includes("/observer/") && currentPath.split("/").length > 2;

    if (eqpId) {
      const newPath = `/observer/${eqpId}`;
      if (currentPath !== newPath) {
        navigate(
          {
            pathname: newPath,
            search: location.search,
            hash: location.hash,
          },
          { replace: true }
        );
      }
    } else if (isParamRoute) {
      navigate(
        {
          pathname: "/observer",
          search: location.search,
          hash: location.hash,
        },
        { replace: true }
      );
    }
  }, [
    eqpId,
    hasValidationResult,
    isValidating,
    location.hash,
    location.pathname,
    location.search,
    navigate,
  ]);

  useEffect(() => {
    resetSelection();
  }, [eqpId, resetSelection]);

  // EQP가 바뀔 때마다 TIP 필터를 초기화하여 예전 선택이 남지 않도록 한다.
  useEffect(() => {
    if (eqpId) {
      setSelectedTipGroups(["__ALL__"]);
    }
  }, [eqpId, setSelectedTipGroups]);

  const handleFilterChange = (event) => {
    const { name, checked } = event.target;
    setTypeFilters((prev) => ({ ...prev, [name]: checked }));
  };

  const logs = useObserverLogs(
    eqpId,
    typeFilters,
    selectedTipGroups,
    logQueryOptions
  );
  const selectedLog =
    logs.mergedLogs.find((log) => String(log.id) === String(selectedRow)) ||
    null;

  return {
    selection: {
      lineId,
      sdwtId,
      prcGroup,
      eqpId,
      setLine,
      setSdwt,
      setPrcGroup,
      setEqp,
      selectedRow,
    },
    observerPrefs: {
      showLegend,
      selectedTipGroups,
      setShowLegend,
      setSelectedTipGroups,
    },
    filters: {
      typeFilters,
      handleFilterChange,
    },
    settings: {
      isSettingsOpen,
      setIsSettingsOpen,
      logRange,
      setLogRange,
    },
    validation: { isValidating, validationError },
    logs,
    selectedLog,
    observerReady: Boolean(eqpId),
  };
}
