import { useState } from "react"
import { AlertTriangle, Database } from "lucide-react"

import { PmSpiderFilterBar } from "../components/PmSpiderFilterBar"
import { PmSpiderCategoryDashboard } from "../components/PmSpiderCategoryDashboard"
import { usePmSpiderMeta, usePmSpiderCategoryResults } from "../hooks/usePmSpiderQueries"
import { DEFAULT_PM_FORM, buildPmSpiderPayload } from "../utils/format"

function ErrorBanner({ error }) {
  if (!error) return null
  return (
    <div className="mx-6 mt-3 flex shrink-0 items-center gap-2 rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
      <AlertTriangle className="size-4" aria-hidden="true" />
      <span>{error.message || "PM Spider 데이터를 불러오지 못했습니다."}</span>
    </div>
  )
}

function EmptyState() {
  return (
    <div className="flex h-full min-h-0 items-center justify-center p-6">
      <div className="grid justify-items-center gap-3 rounded-lg border border-dashed bg-card px-8 py-10 text-center text-sm text-muted-foreground">
        <Database className="size-7" aria-hidden="true" />
        <div>
          <p className="font-medium text-foreground">PM Spider 조건을 입력하세요.</p>
          <p className="mt-1">Line ID, EQP ID, FDC Bin, PM 시점을 선택하면 랭킹을 조회합니다.</p>
        </div>
      </div>
    </div>
  )
}

function buildFilterOptionsMeta({
  lineMeta,
  eqpMeta,
  fdcMeta,
  pmDateMeta,
  selectedMeta,
  form,
}) {
  return {
    ...selectedMeta,
    lineIds: lineMeta?.lineIds ?? selectedMeta?.lineIds ?? [],
    eqpIds: form.lineId ? (eqpMeta?.eqpIds ?? selectedMeta?.eqpIds ?? []) : [],
    fdcBins: form.lineId && form.eqpId ? (fdcMeta?.fdcBins ?? selectedMeta?.fdcBins ?? []) : [],
    pmDates: form.lineId && form.eqpId && form.fdcBin
      ? (pmDateMeta?.pmDates ?? selectedMeta?.pmDates ?? [])
      : [],
  }
}

export function PmSpiderPage() {
  const [form, setForm] = useState(DEFAULT_PM_FORM)
  const [payload, setPayload] = useState(null)
  const [selectedCategoryId, setSelectedCategoryId] = useState("ag")
  const metaQuery = usePmSpiderMeta(form)
  const lineOptionsQuery = usePmSpiderMeta({})
  const eqpOptionsQuery = usePmSpiderMeta({ lineId: form.lineId })
  const fdcOptionsQuery = usePmSpiderMeta({ lineId: form.lineId, eqpId: form.eqpId })
  const pmDateOptionsQuery = usePmSpiderMeta({
    lineId: form.lineId,
    eqpId: form.eqpId,
    fdcBin: form.fdcBin,
  })
  const categoryResults = usePmSpiderCategoryResults(payload, null)
  const filterOptionsMeta = buildFilterOptionsMeta({
    lineMeta: lineOptionsQuery.data,
    eqpMeta: eqpOptionsQuery.data,
    fdcMeta: fdcOptionsQuery.data,
    pmDateMeta: pmDateOptionsQuery.data,
    selectedMeta: metaQuery.data,
    form,
  })
  const isFilterMetaFetching =
    metaQuery.isFetching ||
    lineOptionsQuery.isFetching ||
    eqpOptionsQuery.isFetching ||
    fdcOptionsQuery.isFetching ||
    pmDateOptionsQuery.isFetching

  const updateForm = (nextForm) => {
    setForm(nextForm)
    setPayload(null)
  }

  const submit = () => {
    setPayload(buildPmSpiderPayload(form))
  }

  return (
    <div className="flex h-full min-h-0 min-w-0 flex-col overflow-hidden bg-muted/30">
      <PmSpiderFilterBar
        form={form}
        meta={filterOptionsMeta}
        isMetaLoading={isFilterMetaFetching}
        isResultFetching={categoryResults.isFetching}
        onFormChange={updateForm}
        onSubmit={submit}
      />

      <ErrorBanner error={metaQuery.error || categoryResults.error} />

      <main className="flex-1 min-h-0 overflow-y-auto px-4 py-4 md:px-6">
        {!payload ? (
          <EmptyState />
        ) : categoryResults.isLoading ? (
          <div className="flex h-full min-h-0 items-center justify-center rounded-lg border bg-card text-sm text-muted-foreground">
            PM Spider category 데이터를 계산하는 중입니다.
          </div>
        ) : (
          <PmSpiderCategoryDashboard
            categories={categoryResults.categories}
            meta={metaQuery.data}
            selectedCategoryId={selectedCategoryId}
            onSelectedCategoryChange={setSelectedCategoryId}
            isFetching={categoryResults.isFetching}
          />
        )}
      </main>
    </div>
  )
}
