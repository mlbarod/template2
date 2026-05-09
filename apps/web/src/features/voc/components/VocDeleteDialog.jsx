import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"

export function VocDeleteDialog({
  deleteTarget,
  onOpenChange,
  onCancel,
  onConfirm,
}) {
  return (
    <Dialog open={Boolean(deleteTarget)} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-sm" aria-describedby="voc-delete-description">
        <DialogHeader>
          <DialogTitle>게시글 삭제</DialogTitle>
          <DialogDescription id="voc-delete-description">
            {`"${deleteTarget?.title || "선택한 게시글"}"을(를) 삭제할까요?`}
            <br />
            답변을 포함해 게시글의 모든 내용이 사라집니다.
          </DialogDescription>
        </DialogHeader>
        <div className="rounded-md bg-muted/60 px-3 py-2 text-xs text-muted-foreground">
          {deleteTarget?.title || deleteTarget?.id || "선택한 게시글"}
        </div>
        <DialogFooter className="sm:justify-end">
          <Button type="button" variant="ghost" onClick={onCancel}>
            취소
          </Button>
          <Button type="button" variant="destructive" onClick={onConfirm}>
            삭제
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
