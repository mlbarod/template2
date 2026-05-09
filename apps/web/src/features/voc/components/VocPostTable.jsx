import { Loader2 } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/common"
import { DEFAULT_APP_CATEGORY } from "../utils/constants"
import { formatTimestamp } from "../utils"
import { VocStatusBadge } from "./VocStatusBadge"

export function VocPostTable({
  isLoading,
  isRefreshing,
  filteredPosts,
  visiblePosts,
  statusFilter,
  selectedPost,
  pagination,
  onSelectPost,
}) {
  return (
    <div
      className="min-h-0 overflow-y-auto rounded-lg border bg-background"
      aria-busy={isLoading || isRefreshing}
    >
      <Table stickyHeader className="table-fixed [&_th]:text-center [&_td]:text-center">
        <TableHeader>
          <TableRow>
            <TableHead className="w-[70px]">No</TableHead>
            <TableHead className="w-[45%] min-w-[260px]">제목</TableHead>
            <TableHead className="w-[120px]">카테고리</TableHead>
            <TableHead className="w-[120px]">상태</TableHead>
            <TableHead className="w-[120px]">작성자</TableHead>
            <TableHead className="w-[150px]">작성일</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {isLoading ? (
            <TableRow>
              <TableCell colSpan={6} className="text-center text-sm text-muted-foreground">
                <span className="inline-flex items-center justify-center gap-2">
                  <Loader2 className="size-4 animate-spin" aria-hidden="true" />
                  <span>VOC 게시글을 불러오는 중입니다...</span>
                </span>
              </TableCell>
            </TableRow>
          ) : filteredPosts.length === 0 ? (
            <TableRow>
              <TableCell colSpan={6} className="text-center text-sm text-muted-foreground">
                {statusFilter
                  ? "선택한 상태의 글이 없습니다."
                  : "아직 등록된 글이 없습니다. 첫 문의를 남겨보세요."}
              </TableCell>
            </TableRow>
          ) : (
            visiblePosts.map((post, index) => {
              const isSelected = post.id === selectedPost?.id
              const displayNumber = Math.max(
                pagination.totalRows - (pagination.pageIndex * pagination.pageSize + index),
                1,
              )
              return (
                <TableRow
                  key={post.id}
                  onClick={() => onSelectPost(post.id)}
                  className={`cursor-pointer ${
                    isSelected ? "bg-muted/60" : "hover:bg-muted/40"
                  }`}
                  data-selected={isSelected ? "true" : undefined}
                >
                  <TableCell className="w-[90px] text-sm font-semibold text-muted-foreground">
                    {displayNumber}
                  </TableCell>
                  <TableCell className="w-[45%] min-w-[260px] font-medium">
                    {post.title}
                  </TableCell>
                  <TableCell className="w-[120px]">
                    <Badge variant="outline" className="text-[11px]">
                      {post.app || DEFAULT_APP_CATEGORY}
                    </Badge>
                  </TableCell>
                  <TableCell className="w-[120px]">
                    <VocStatusBadge status={post.status} />
                  </TableCell>
                  <TableCell className="w-[120px]">
                    {post.author?.name || "작성자"}
                  </TableCell>
                  <TableCell className="w-[150px] text-xs text-muted-foreground">
                    {formatTimestamp(post.createdAt)}
                  </TableCell>
                </TableRow>
              )
            })
          )}
        </TableBody>
      </Table>
    </div>
  )
}
