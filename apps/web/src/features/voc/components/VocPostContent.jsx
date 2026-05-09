import * as React from "react"

import { sanitizeContentHtml } from "../utils"

export function VocPostContent({ content, className = "", allowResize = false }) {
  const safeHtml = React.useMemo(() => sanitizeContentHtml(content), [content])
  const containerClassName = [
    "overflow-x-auto overflow-y-auto rounded-md border border-input bg-muted/20 px-3 py-3 shadow-xs min-w-full max-w-full",
    className,
  ]
    .filter(Boolean)
    .join(" ")

  const bodyClassName = [
    "voc-post-body",
    allowResize ? "voc-post-body--resizable" : "",
  ]
    .filter(Boolean)
    .join(" ")

  return (
    <div className={containerClassName}>
      {safeHtml ? (
        <div className={bodyClassName} dangerouslySetInnerHTML={{ __html: safeHtml }} />
      ) : (
        <p className="text-sm text-muted-foreground">내용이 없습니다.</p>
      )}
    </div>
  )
}
