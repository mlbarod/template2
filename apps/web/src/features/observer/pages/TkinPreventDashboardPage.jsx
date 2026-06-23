import React, { useState } from "react";
import { RefreshCw, RotateCcw, TableProperties } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

import { LoadingSpinner } from "../components/Loaders";
import {
  useLines,
  usePrcGroups,
  useSDWT,
} from "../hooks/useLineQueries";
import {
  useTkinPreventMatrix,
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
            : "라인, SDWT, PRC Group, process_id, step_seq를 선택하면 matrix가 표시됩니다."}
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
      {values.map((value) => (
        <Badge
          key={`${value.status}-${value.type}-${value.registrationLevel}`}
          variant={value.status === "DOING" ? "default" : "secondary"}
          className="max-w-full justify-start truncate rounded-md"
          title={value.status}
        >
          {value.status}
        </Badge>
      ))}
    </div>
  );
}

function TkinPreventMatrixTable({ matrix }) {
  const columns = matrix?.columns || [];
  const rows = matrix?.rows || [];

  if (!columns.length || !rows.length) {
    return <EmptyPanel ready={true} />;
  }

  return (
    <div className="h-full min-h-0 min-w-0 overflow-auto">
      <table className="min-w-full border-separate border-spacing-0 text-sm">
        <thead>
          <tr>
            <th className="sticky left-0 top-0 z-20 min-w-48 border-b border-r bg-card px-3 py-2 text-left text-xs font-semibold text-muted-foreground">
              ppid
            </th>
            {columns.map((column) => (
              <th
                key={column.id}
                className="sticky top-0 z-10 min-w-44 border-b border-r bg-card px-3 py-2 text-left text-xs font-semibold text-muted-foreground"
              >
                <div className="grid gap-0.5">
                  <span className="truncate text-foreground" title={column.label}>
                    {column.label}
                  </span>
                  <span className="truncate font-normal">
                    {column.eqpId} / {column.chamberId}
                  </span>
                </div>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.ppid} className="hover:bg-muted/40">
              <th className="sticky left-0 z-10 min-w-48 border-b border-r bg-card px-3 py-2 text-left align-top text-xs font-semibold text-foreground">
                <span className="block max-w-48 truncate" title={row.ppid}>
                  {row.ppid}
                </span>
              </th>
              {columns.map((column) => (
                <td
                  key={`${row.ppid}-${column.id}`}
                  className="min-w-44 border-b border-r px-3 py-2 align-top"
                >
                  <MatrixCell values={row.cells?.[column.id]} />
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
  const [lineId, setLineId] = useState("");
  const [sdwtId, setSdwtId] = useState("");
  const [prcGroup, setPrcGroup] = useState("");
  const [processId, setProcessId] = useState("");
  const [stepSeq, setStepSeq] = useState("");

  const linesQuery = useLines();
  const sdwtQuery = useSDWT(lineId);
  const prcGroupsQuery = usePrcGroups(lineId, sdwtId);
  const processesQuery = useTkinPreventProcesses(lineId, sdwtId, prcGroup);
  const stepSeqsQuery = useTkinPreventStepSeqs(
    lineId,
    sdwtId,
    prcGroup,
    processId
  );
  const matrixQuery = useTkinPreventMatrix(
    lineId,
    sdwtId,
    prcGroup,
    processId,
    stepSeq
  );

  const matrixReady = !!lineId && !!sdwtId && !!prcGroup && !!processId && !!stepSeq;
  const matrix = matrixQuery.data || { columns: [], rows: [] };

  const resetFilters = () => {
    setLineId("");
    setSdwtId("");
    setPrcGroup("");
    setProcessId("");
    setStepSeq("");
  };

  const handleLineChange = (value) => {
    setLineId(value);
    setSdwtId("");
    setPrcGroup("");
    setProcessId("");
    setStepSeq("");
  };

  const handleSdwtChange = (value) => {
    setSdwtId(value);
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
    linesQuery.error ||
    sdwtQuery.error ||
    prcGroupsQuery.error ||
    processesQuery.error ||
    stepSeqsQuery.error;

  return (
    <div className="flex h-full min-h-0 flex-col gap-4">
      <div className="shrink-0 rounded-xl border bg-card px-4 py-3">
        <div className="flex items-start justify-between gap-4">
          <div className="grid gap-1">
            <h1 className="text-2xl font-semibold tracking-tight">
              T/K-IN Prevent Dashboard
            </h1>
            <p className="text-sm text-muted-foreground">
              m_tkin_prevent 기준 예방 상태 matrix
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
          <div className="grid grid-cols-5 gap-3">
            <SelectField
              id="tkin-prevent-line"
              label="Line"
              value={lineId}
              options={linesQuery.data || []}
              placeholder="Line 선택"
              loading={linesQuery.isLoading}
              onChange={handleLineChange}
            />
            <SelectField
              id="tkin-prevent-sdwt"
              label="SDWT"
              value={sdwtId}
              options={sdwtQuery.data || []}
              placeholder="SDWT 선택"
              disabled={!lineId}
              loading={sdwtQuery.isLoading}
              onChange={handleSdwtChange}
            />
            <SelectField
              id="tkin-prevent-prc-group"
              label="PRC Group"
              value={prcGroup}
              options={prcGroupsQuery.data || []}
              placeholder="PRC Group 선택"
              disabled={!lineId || !sdwtId}
              loading={prcGroupsQuery.isLoading}
              onChange={handlePrcGroupChange}
            />
            <SelectField
              id="tkin-prevent-process"
              label="process_id"
              value={processId}
              options={processesQuery.data || []}
              placeholder="process_id 선택"
              disabled={!lineId || !sdwtId || !prcGroup}
              loading={processesQuery.isLoading}
              onChange={handleProcessChange}
            />
            <SelectField
              id="tkin-prevent-step-seq"
              label="step_seq"
              value={stepSeq}
              options={stepSeqsQuery.data || []}
              placeholder="step_seq 선택"
              disabled={!lineId || !sdwtId || !prcGroup || !processId}
              loading={stepSeqsQuery.isLoading}
              onChange={setStepSeq}
            />
          </div>

          <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
            <Badge variant="outline">Rows {matrix.totalRows ?? 0}</Badge>
            <Badge variant="outline">Columns {matrix.totalColumns ?? 0}</Badge>
            {filterError ? (
              <span className="text-destructive">필터 데이터를 불러오지 못했습니다.</span>
            ) : null}
          </div>
        </div>
      </section>

      <section className="min-h-0 min-w-0 flex-1 overflow-hidden rounded-xl border bg-card">
        <div className="grid h-full min-h-0 grid-rows-[auto,1fr]">
          <div className="shrink-0 border-b px-4 py-3">
            <h2 className="text-base font-semibold">Prevent Matrix</h2>
          </div>
          <div className="min-h-0 min-w-0">
            {matrixQuery.isFetching ? (
              <div className="flex h-full items-center justify-center">
                <LoadingSpinner label="matrix를 불러오는 중입니다" />
              </div>
            ) : matrixQuery.error ? (
              <ErrorPanel
                title="matrix 조회 실패"
                message={matrixQuery.error.message}
                onRetry={() => matrixQuery.refetch()}
              />
            ) : matrixReady ? (
              <TkinPreventMatrixTable matrix={matrix} />
            ) : (
              <EmptyPanel ready={false} />
            )}
          </div>
        </div>
      </section>
    </div>
  );
}
