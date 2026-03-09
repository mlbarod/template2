import { useState } from "react"

import {
  ChevronDownIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  ChevronUpIcon,
  CrownIcon,
  EyeIcon,
  UserRoundIcon,
} from "lucide-react"

import {
  flexRender,
  getCoreRowModel,
  getPaginationRowModel,
  getSortedRowModel,
  useReactTable,
} from "@tanstack/react-table"

import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Pagination,
  PaginationContent,
  PaginationEllipsis,
  PaginationItem,
} from "@/components/ui/pagination"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/common"

import { cn } from "@/lib/utils"
import { buildProfileImageUrl, resolveProfileAvatarId } from "@/lib/profileImage"

const ROLE_LABELS = {
  viewer: "뷰어",
  member: "멤버",
  manager: "관리자",
}

const ROLE_VARIANTS = {
  viewer: "secondary",
  member: "outline",
  manager: "default",
}

function resolveRole(value) {
  return ROLE_LABELS[value] ? value : "viewer"
}

const COLUMNS = [
  {
    header: "사용자",
    accessorKey: "username",
    cell: ({ row }) => {
      const username = row.getValue("username")
      const primary =
        typeof username === "string" && username.trim()
          ? username
          : row.original.user || row.original.name || "Unknown"
      const knoxId = row.original.knoxId || row.original.knox_id || row.original.secondary || ""
      const profileAvatarId = resolveProfileAvatarId(row.original)
      const avatarSrc = buildProfileImageUrl(profileAvatarId)

      return (
        <div className="flex items-center gap-2">
          <Avatar className="size-9">
            <AvatarImage src={avatarSrc || undefined} alt={primary} />
            <AvatarFallback className="text-xs">{row.original.fallback}</AvatarFallback>
          </Avatar>
          <div className="flex min-w-0 gap-2">
            <span className="truncate font-medium">{primary}</span>
            {knoxId ? (
              <span className="truncate text-muted-foreground">({knoxId})</span>
            ) : null}
          </div>
        </div>
      )
    },
    size: 360,
  },
  {
    header: "권한",
    accessorKey: "role",
    cell: ({ row }) => {
      const role = resolveRole(row.getValue("role"))
      const isManager = role === "manager"
      const isMember = role === "member"
      const Icon = isManager ? CrownIcon : isMember ? UserRoundIcon : EyeIcon

      return (
        <div className="flex items-center gap-2">
          <Icon
            className={cn(
              "size-4",
              isManager ? "text-primary" : "text-muted-foreground",
            )}
            aria-hidden="true"
          />
          <Badge variant={ROLE_VARIANTS[role]}>{ROLE_LABELS[role]}</Badge>
        </div>
      )
    },
    size: 180,
  },
  {
    id: "emailCount",
    header: () => <div className="text-right">메일 수</div>,
    accessorKey: "emailCount",
    cell: ({ row }) => {
      const value = row.getValue("emailCount")
      const safeNumber = typeof value === "number" ? value : 0

      return <div className="text-right tabular-nums">{safeNumber.toLocaleString()}</div>
    },
    size: 140,
  },
]

function getPagination({
  currentPage,
  totalPages,
  paginationItemsToDisplay,
}) {
  const safeTotalPages = Number.isFinite(totalPages) ? Math.max(0, totalPages) : 0
  const safeCurrentPage = Number.isFinite(currentPage) ? Math.max(1, currentPage) : 1
  const safeDisplay = Number.isFinite(paginationItemsToDisplay)
    ? Math.max(1, paginationItemsToDisplay)
    : 1

  if (safeTotalPages <= safeDisplay) {
    const pages = Array.from({ length: safeTotalPages }, (_, index) => index + 1)
    return { pages, showLeftEllipsis: false, showRightEllipsis: false }
  }

  const halfDisplay = Math.floor(safeDisplay / 2)
  const initialRange = {
    start: safeCurrentPage - halfDisplay,
    end: safeCurrentPage + halfDisplay,
  }

  const adjustedRange = {
    start: Math.max(1, initialRange.start),
    end: Math.min(safeTotalPages, initialRange.end),
  }

  if (adjustedRange.start === 1) {
    adjustedRange.end = Math.min(safeDisplay, safeTotalPages)
  }

  if (adjustedRange.end === safeTotalPages) {
    adjustedRange.start = Math.max(1, safeTotalPages - safeDisplay + 1)
  }

  const pages = Array.from(
    { length: adjustedRange.end - adjustedRange.start + 1 },
    (_, index) => adjustedRange.start + index,
  )

  const showLeftEllipsis = pages.length > 0 && pages[0] > 2
  const showRightEllipsis = pages.length > 0 && pages[pages.length - 1] < safeTotalPages - 1

  return { pages, showLeftEllipsis, showRightEllipsis }
}

export function EmailMailboxMembersDatatable({ data }) {
  const safeData = Array.isArray(data) ? data : []

  const [pagination, setPagination] = useState({
    pageIndex: 0,
    pageSize: 10,
  })

  const table = useReactTable({
    data: safeData,
    columns: COLUMNS,
    getRowId: (row) => row.id,
    state: {
      pagination,
    },
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    enableSortingRemoval: false,
    onPaginationChange: setPagination,
  })

  const { pageIndex, pageSize } = table.getState().pagination
  const totalRows = table.getRowCount()
  const totalPages = table.getPageCount()
  const start = totalRows === 0 ? 0 : pageIndex * pageSize + 1
  const end = totalRows === 0 ? 0 : Math.min(start + pageSize - 1, totalRows)

  const { pages, showLeftEllipsis, showRightEllipsis } = getPagination({
    currentPage: pageIndex + 1,
    totalPages,
    paginationItemsToDisplay: 2,
  })

  return (
    <div className="grid h-full min-h-0 min-w-0 grid-rows-[1fr_auto]">
      <div className="min-h-0 min-w-0 overflow-y-auto px-4">
        <Table>
          <TableHeader>
            {table.getHeaderGroups().map((headerGroup) => (
              <TableRow key={headerGroup.id} className="h-14 border-t">
                {headerGroup.headers.map((header) => {
                  const isEmailCount = header.column.id === "emailCount"
                  const canSort = header.column.getCanSort()

                  return (
                    <TableHead
                      key={header.id}
                      style={{ width: `${header.getSize()}px` }}
                      className={cn(
                        "text-muted-foreground first:pl-4 last:pr-4",
                        isEmailCount && "text-right",
                      )}
                    >
                      {header.isPlaceholder ? null : canSort ? (
                        <div
                          className={cn(
                            "flex h-full cursor-pointer items-center gap-2 select-none",
                            isEmailCount ? "justify-end" : "justify-between",
                          )}
                          onClick={header.column.getToggleSortingHandler()}
                          onKeyDown={(event) => {
                            if (event.key !== "Enter" && event.key !== " ") return
                            event.preventDefault()
                            header.column.getToggleSortingHandler()?.(event)
                          }}
                          tabIndex={0}
                        >
                          {flexRender(header.column.columnDef.header, header.getContext())}
                          {{
                            asc: (
                              <ChevronUpIcon
                                className="shrink-0 opacity-60"
                                size={16}
                                aria-hidden="true"
                              />
                            ),
                            desc: (
                              <ChevronDownIcon
                                className="shrink-0 opacity-60"
                                size={16}
                                aria-hidden="true"
                              />
                            ),
                          }[header.column.getIsSorted()] ?? null}
                        </div>
                      ) : (
                        flexRender(header.column.columnDef.header, header.getContext())
                      )}
                    </TableHead>
                  )
                })}
              </TableRow>
            ))}
          </TableHeader>
          <TableBody>
            {table.getRowModel().rows?.length ? (
              table.getRowModel().rows.map((row) => (
                <TableRow key={row.id} className="hover:bg-transparent">
                  {row.getVisibleCells().map((cell) => (
                    <TableCell key={cell.id} className="h-14 first:pl-4 last:pr-4">
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </TableCell>
                  ))}
                </TableRow>
              ))
            ) : (
              <TableRow>
                <TableCell
                  colSpan={COLUMNS.length}
                  className="h-24 text-center text-sm text-muted-foreground"
                >
                  멤버가 없습니다.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>

      <div className="flex items-center justify-between gap-3 border-t p-4 max-sm:flex-col">
        <p className="text-sm text-muted-foreground whitespace-nowrap" aria-live="polite">
          표시 {start}–{end} / 총 {totalRows}명
        </p>

        <Pagination>
          <PaginationContent>
            <PaginationItem>
              <Button
                className="disabled:pointer-events-none disabled:opacity-50"
                variant="ghost"
                onClick={() => table.previousPage()}
                disabled={!table.getCanPreviousPage()}
                aria-label="이전 페이지"
              >
                <ChevronLeftIcon aria-hidden="true" />
                이전
              </Button>
            </PaginationItem>

            {showLeftEllipsis ? (
              <PaginationItem>
                <PaginationEllipsis />
              </PaginationItem>
            ) : null}

            {pages.map((page) => {
              const isActive = page === pageIndex + 1

              return (
                <PaginationItem key={page}>
                  <Button
                    size="icon"
                    className={cn(
                      !isActive &&
                      "bg-primary/10 text-primary hover:bg-primary/20 focus-visible:ring-primary/20 dark:focus-visible:ring-primary/40",
                    )}
                    onClick={() => table.setPageIndex(page - 1)}
                    aria-current={isActive ? "page" : undefined}
                  >
                    {page}
                  </Button>
                </PaginationItem>
              )
            })}

            {showRightEllipsis ? (
              <PaginationItem>
                <PaginationEllipsis />
              </PaginationItem>
            ) : null}

            <PaginationItem>
              <Button
                className="disabled:pointer-events-none disabled:opacity-50"
                variant="ghost"
                onClick={() => table.nextPage()}
                disabled={!table.getCanNextPage()}
                aria-label="다음 페이지"
              >
                다음
                <ChevronRightIcon aria-hidden="true" />
              </Button>
            </PaginationItem>
          </PaginationContent>
        </Pagination>
      </div>
    </div>
  )
}
