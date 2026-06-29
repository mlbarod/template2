import React, { useEffect, useMemo, useState } from "react";
import { RefreshCw, RotateCcw, TableProperties } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  useActiveLine,
  useLineDashboardLineSdwtOptionsQuery,
} from "@/lib/affiliation";

import { LoadingSpinner } from "../components/Loaders";
import {
  useTkinPreventMatrix,
  useTkinPreventPrcGroups,
  useTkinPreventProcesses,
  useTkinPreventStepSeqs,
} from "../hooks/useTkinPreventQueries";

function SelectField({
  id,
  label,
  value,
  options,
  placeholder,
  disabled,
  loading,
  onChange,
}) {
  return (
    <label htmlFor={id} className="grid gap-2">
      <span className="text-xs font-medium text-muted-foreground">{label}</span>
      <select
        id={id}
        value={value}
        disabled={disabled || loading}
        onChange={(event) => onChange(event.target.value)}
        className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm text-foreground shadow-xs outline-none transition-colors focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-[3px] disabled:cursor-not-allowed disabled:bg-muted disabled:text-muted-foreground disabled:opacity-70"
      >
        <option value="">{loading ? "불러오는 중" : placeholder}</option>
        {options.map((option) => (
          <option key={option.id} value={option.id}>
            {option.name}
          </option>
        ))}
      </select>
    </label>
  );
}

function ErrorPanel({ title, message, onRetry }) {
  return (
    <div className="flex h-full min-h-0 items-center justify-center p-6">
      <div className="grid max-w-md gap-3 text-center">
        <div className="text-base font-semibold text-foreground">{title}</div>
        <p className="text-sm text-muted-foreground">{message}</p>
        {onRetry ? (
          <Button type="button" variant="outline" size="sm" onClick={onRetry}>
            <RefreshCw className="size-4" />
            다시 조회
          </Button>
        ) : null}
      </div>
    </div>
  );
}

function EmptyPanel({ ready }) {
  return (
    <div className="flex h-full min-h-0 items-center justify-center p-6">
      <div className="grid max-w-md justify-items-center gap-3 text-center">
        <div className="rounded-full border bg-muted p-3 text-muted-foreground">
          <TableProperties className="size-6" />
        </div>
        <div className="text-base font-semibold text-foreground">
          {ready ? "조회 결과가 없습니다" : "조회 조건을 선택하세요"}
        </div>
        <p className="text-sm leading-6 text-muted-foreground">
          {ready
            ? "선택한 process_id와 step_seq에 해당하는 m_tkin_prevent row가 없습니다."
            : "Line, user_sdwt_prod, PRC Group, process_id, step_seq를 선택하면 예방 상태 표가 표시됩니다."}
        </p>
      </div>
    </div>
  );
}

function MatrixCell({ values }) {
  if (!values?.length) {
    return <span className="text-muted-foreground">-</span>;
  }

  return (
    <div className="grid gap-1">
      {values.map((value, index) => {
        const comment = normalizeOptionValue(value.comment);
        const badge = (
          <Badge
            variant={value.status === "DOING" ? "default" : "secondary"}
            className="max-w-full justify-start truncate rounded-md"
            tabIndex={comment ? 0 : undefined}
            aria-label={comment ? `${value.status} ${comment}` : value.status}
          >
            {value.status}
          </Badge>
        );

        if (!comment) {
          return React.cloneElement(badge, {
            key: `${value.status}-${value.type}-${value.registrationLevel}-${index}`,
          });
        }

        return (
          <Tooltip key={`${value.status}-${value.type}-${value.registrationLevel}-${comment}-${index}`}>
            <TooltipTrigger asChild>{badge}</TooltipTrigger>
            <TooltipContent side="top" align="start" className="max-w-96 whitespace-pre-wrap text-left leading-5">
              {comment}
            </TooltipContent>
          </Tooltip>
        );
      })}
    </div>
  );
}

function normalizeOptionValue(value) {
  if (value === null || value === undefined) return "";
  return typeof value === "string" ? value.trim() : String(value).trim();
}

function getUserSdwtOptionsForLine(payload, lineId) {
  const normalizedLineId = normalizeOptionValue(lineId).toLowerCase();
  const lines = Array.isArray(payload?.lines) ? payload.lines : [];
  const line = lines.find(
    (item) => normalizeOptionValue(item?.lineId).toLowerCase() === normalizedLineId
  );
  const values = Array.isArray(line?.userSdwtProds) ? line.userSdwtProds : [];

  return values
    .map((value) => normalizeOptionValue(value))
    .filter(Boolean)
    .map((value) => ({ id: value, name: value }));
}

function getUniquePpidColumns(rows) {
  const columnsByPpid = new Map();

  rows.forEach((row) => {
    if (!row?.ppid) return;
    if (!columnsByPpid.has(row.ppid)) {
      columnsByPpid.set(row.ppid, { ...row, cells: { ...(row.cells || {}) } });
      return;
    }

    const current = columnsByPpid.get(row.ppid);
    Object.entries(row.cells || {}).forEach(([equipmentId, values]) => {
      current.cells[equipmentId] = [
        ...(current.cells[equipmentId] || []),
        ...(Array.isArray(values) ? values : []),
      ];
    });
  });

  return Array.from(columnsByPpid.values());
}

function getEquipmentDisplayRows(columns) {
  const originalIndexById = new Map(
    columns.map((column, index) => [column.id, index])
  );
  const seenEquipmentKeys = new Set();
  const sortedColumns = [...columns].sort((left, right) => {
    const leftLineId = left.lineId || "-";
    const rightLineId = right.lineId || "-";
    const leftEqpId = left.eqpId || "-";
    const rightEqpId = right.eqpId || "-";

    if (leftLineId !== rightLineId) {
      return originalIndexById.get(left.id) - originalIndexById.get(right.id);
    }

    if (leftEqpId !== rightEqpId) {
      return originalIndexById.get(left.id) - originalIndexById.get(right.id);
    }

    const leftIsMain = normalizeOptionValue(left.chamberId).toUpperCase() === "MAIN";
    const rightIsMain = normalizeOptionValue(right.chamberId).toUpperCase() === "MAIN";

    if (leftIsMain && !rightIsMain) return -1;
    if (!leftIsMain && rightIsMain) return 1;

    return originalIndexById.get(left.id) - originalIndexById.get(right.id);
  });

  return sortedColumns.map((column) => {
    const lineId = column.lineId || "-";
    const eqpId = column.eqpId || "-";
    const equipmentKey = `${lineId}\0${eqpId}`;
    const showEquipment = !seenEquipmentKeys.has(equipmentKey);
    seenEquipmentKeys.add(equipmentKey);

    return {
      ...column,
      lineId,
      eqpId,
      chamberId: column.chamberId || "-",
      showEquipment,
    };
  });
}

function TkinPreventMatrixTable({ matrix }) {
  const equipmentRows = useMemo(
    () => getEquipmentDisplayRows(matrix?.columns || []),
    [matrix]
  );
  const ppidColumns = useMemo(
    () => getUniquePpidColumns(matrix?.rows || []),
    [matrix]
  );

  if (!equipmentRows.length || !ppidColumns.length) {
    return <EmptyPanel ready={true} />;
  }

  return (
    <div className="h-full min-h-0 min-w-0 overflow-auto">
      <table className="min-w-full border-separate border-spacing-0 text-sm">
        <thead>
          <tr>
            <th className="sticky left-0 top-0 z-30 w-24 min-w-24 border-b border-r bg-card px-2 py-1 text-left text-xs font-semibold leading-tight text-muted-foreground">
              line_id
            </th>
            <th className="sticky left-24 top-0 z-30 w-32 min-w-32 border-b border-r bg-card px-2 py-1 text-left text-xs font-semibold leading-tight text-muted-foreground">
              EQP ID
            </th>
            <th className="sticky left-56 top-0 z-30 w-24 min-w-24 border-b border-r bg-card px-2 py-1 text-left text-xs font-semibold leading-tight text-muted-foreground">
              CH
            </th>
            {ppidColumns.map((ppidColumn) => (
              <th
                key={ppidColumn.ppid}
                className="sticky top-0 z-10 min-w-44 border-b border-r bg-card px-2 py-1 text-left text-xs font-semibold leading-tight text-foreground"
                title={ppidColumn.ppid}
              >
                <span className="block truncate">{ppidColumn.ppid}</span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {equipmentRows.map((equipmentRow) => (
            <tr key={equipmentRow.id} className="hover:bg-muted/40">
              <th className="sticky left-0 z-20 w-24 min-w-24 border-b border-r bg-card px-3 py-2 text-left align-top text-xs font-semibold text-foreground">
                <span
                  className="block max-w-20 truncate"
                  title={equipmentRow.lineId}
                >
                  {equipmentRow.showEquipment ? equipmentRow.lineId : ""}
                </span>
              </th>
              <th className="sticky left-24 z-20 w-32 min-w-32 border-b border-r bg-card px-3 py-2 text-left align-top text-xs font-semibold text-foreground">
                <span
                  className="block max-w-28 truncate"
                  title={equipmentRow.eqpId}
                >
                  {equipmentRow.showEquipment ? equipmentRow.eqpId : ""}
                </span>
              </th>
              <th className="sticky left-56 z-20 w-24 min-w-24 border-b border-r bg-card px-3 py-2 text-left align-top text-xs font-medium text-foreground">
                <span className="block max-w-20 truncate" title={equipmentRow.chamberId}>
                  {equipmentRow.chamberId}
                </span>
              </th>
              {ppidColumns.map((ppidColumn) => (
                <td
                  key={`${equipmentRow.id}-${ppidColumn.ppid}`}
                  className="min-w-44 border-b border-r px-3 py-2 align-top"
                >
                  <MatrixCell values={ppidColumn.cells?.[equipmentRow.id]} />
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function TkinPreventDashboardPage() {
  const { lineId } = useActiveLine();
  const [userSdwtProd, setUserSdwtProd] = useState("");
  const [prcGroup, setPrcGroup] = useState("");
  const [processId, setProcessId] = useState("");
  const [stepSeq, setStepSeq] = useState("");

  const lineSdwtOptionsQuery = useLineDashboardLineSdwtOptionsQuery();
  const userSdwtOptions = useMemo(
    () => getUserSdwtOptionsForLine(lineSdwtOptionsQuery.data, lineId),
    [lineSdwtOptionsQuery.data, lineId]
  );
  const prcGroupsQuery = useTkinPreventPrcGroups(userSdwtProd);
  const processesQuery = useTkinPreventProcesses(userSdwtProd, prcGroup);
  const stepSeqsQuery = useTkinPreventStepSeqs(
    userSdwtProd,
    prcGroup,
    processId
  );
  const matrixQuery = useTkinPreventMatrix(
    userSdwtProd,
    prcGroup,
    processId,
    stepSeq
  );

  const matrixReady = !!lineId && !!userSdwtProd && !!prcGroup && !!processId && !!stepSeq;
  const matrix = matrixQuery.data || { columns: [], rows: [] };

  const resetFilters = () => {
    setUserSdwtProd("");
    setPrcGroup("");
    setProcessId("");
    setStepSeq("");
  };

  useEffect(() => {
    setUserSdwtProd("");
    setPrcGroup("");
    setProcessId("");
    setStepSeq("");
  }, [lineId]);

  useEffect(() => {
    if (!userSdwtProd) return;
    const hasSelectedOption = userSdwtOptions.some((option) => option.id === userSdwtProd);
    if (hasSelectedOption) return;

    setUserSdwtProd("");
    setPrcGroup("");
    setProcessId("");
    setStepSeq("");
  }, [userSdwtOptions, userSdwtProd]);

  const handleUserSdwtProdChange = (value) => {
    setUserSdwtProd(value);
    setPrcGroup("");
    setProcessId("");
    setStepSeq("");
  };

  const handlePrcGroupChange = (value) => {
    setPrcGroup(value);
    setProcessId("");
    setStepSeq("");
  };

  const handleProcessChange = (value) => {
    setProcessId(value);
    setStepSeq("");
  };

  const filterError =
    lineSdwtOptionsQuery.error ||
    prcGroupsQuery.error ||
    processesQuery.error ||
    stepSeqsQuery.error;

  return (
    <div className="flex h-full min-h-0 flex-col gap-4">
      <div className="shrink-0 rounded-xl border bg-card px-4 py-3">
        <div className="flex items-start justify-between gap-4">
          <div className="grid gap-1">
            <h1 className="text-2xl font-semibold tracking-tight">
              Tkin Prevent Dashboard
            </h1>
            <p className="text-sm text-muted-foreground">
              {lineId ? `${lineId} TIP현황` : "Line을 선택하세요"}
            </p>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            <Button type="button" variant="outline" size="sm" onClick={resetFilters}>
              <RotateCcw className="size-4" />
              초기화
            </Button>
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={!matrixReady || matrixQuery.isFetching}
              onClick={() => matrixQuery.refetch()}
            >
              <RefreshCw className="size-4" />
              새로고침
            </Button>
          </div>
        </div>
      </div>

      <section className="shrink-0 rounded-xl border bg-card">
        <div className="grid gap-4 p-4">
          <div className="grid grid-cols-4 gap-3">
            <SelectField
              id="tkin-prevent-user-sdwt-prod"
              label="user_sdwt_prod"
              value={userSdwtProd}
              options={userSdwtOptions}
              placeholder={lineId ? "user_sdwt_prod 선택" : "Line 선택 필요"}
              disabled={!lineId}
              loading={lineSdwtOptionsQuery.isLoading}
              onChange={handleUserSdwtProdChange}
            />
            <SelectField
              id="tkin-prevent-prc-group"
              label="PRC Group"
              value={prcGroup}
              options={prcGroupsQuery.data || []}
              placeholder="PRC Group 선택"
              disabled={!lineId || !userSdwtProd}
              loading={prcGroupsQuery.isLoading}
              onChange={handlePrcGroupChange}
            />
            <SelectField
              id="tkin-prevent-process"
              label="process_id"
              value={processId}
              options={processesQuery.data || []}
              placeholder="process_id 선택"
              disabled={!lineId || !userSdwtProd || !prcGroup}
              loading={processesQuery.isLoading}
              onChange={handleProcessChange}
            />
            <SelectField
              id="tkin-prevent-step-seq"
              label="step_seq"
              value={stepSeq}
              options={stepSeqsQuery.data || []}
              placeholder="step_seq 선택"
              disabled={!lineId || !userSdwtProd || !prcGroup || !processId}
              loading={stepSeqsQuery.isLoading}
              onChange={setStepSeq}
            />
          </div>

          <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
            <Badge variant="outline">PPID {matrix.totalRows ?? 0}</Badge>
            <Badge variant="outline">EQP-CH {matrix.totalColumns ?? 0}</Badge>
            {filterError ? (
              <span className="text-destructive">필터 데이터를 불러오지 못했습니다.</span>
            ) : null}
          </div>
        </div>
      </section>

      <section className="min-h-0 min-w-0 flex-1 overflow-hidden rounded-xl border bg-card">
        <div className="h-full min-h-0 min-w-0">
          {matrixQuery.isFetching ? (
            <div className="flex h-full items-center justify-center">
              <LoadingSpinner label="예방 상태 표를 불러오는 중입니다" />
            </div>
          ) : matrixQuery.error ? (
            <ErrorPanel
              title="예방 상태 표 조회 실패"
              message={matrixQuery.error.message}
              onRetry={() => matrixQuery.refetch()}
            />
          ) : matrixReady ? (
            <TkinPreventMatrixTable matrix={matrix} />
          ) : (
            <EmptyPanel ready={false} />
          )}
        </div>
      </section>
    </div>
  );
}
