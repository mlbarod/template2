import React from "react";
import { createPortal } from "react-dom";
import { ExternalLink, ImageIcon, X } from "lucide-react";
import Field from "./Field";

function getDefectImageUrls(item) {
  if (!Array.isArray(item?.imageUrls)) return [];
  return item.imageUrls
    .map((url) => (typeof url === "string" ? url.trim() : ""))
    .filter(Boolean);
}

function DefectMapLink({ item, index }) {
  const [open, setOpen] = React.useState(false);
  const imageUrls = getDefectImageUrls(item);
  const label = item.label || `Defect Map ${index + 1}`;

  return (
    <>
      <button
        type="button"
        className="inline-flex items-center gap-1 text-primary underline break-all transition-colors hover:text-primary/80 focus:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
        title={imageUrls[0] || item.url}
        aria-label={`${label} defect map 팝업 열기`}
        onClick={() => setOpen(true)}
      >
        <ImageIcon className="h-3.5 w-3.5 shrink-0" />
        {label}
      </button>
      <DefectMapPopup
        item={item}
        label={label}
        imageUrls={imageUrls}
        open={open}
        onOpenChange={setOpen}
      />
    </>
  );
}

function DefectMapPopup({ item, label, imageUrls, open, onOpenChange }) {
  React.useEffect(() => {
    if (!open) return undefined;

    function handleKeyDown(event) {
      if (event.key === "Escape") {
        onOpenChange(false);
      }
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onOpenChange, open]);

  if (!open || typeof document === "undefined") return null;

  const isSingleImage = imageUrls.length === 1;

  return createPortal(
    <div
      className="fixed inset-0 z-[70] flex cursor-default items-center justify-center bg-background/40 px-4 py-6 backdrop-blur-[1px]"
      onClick={() => onOpenChange(false)}
    >
      <div
        className={`flex max-h-[min(78vh,760px)] ${isSingleImage ? "w-[min(520px,calc(100vw-2rem))]" : "w-[min(820px,calc(100vw-2rem))]"} cursor-auto flex-col overflow-hidden rounded-xl border border-border bg-popover shadow-xl`}
        role="dialog"
        aria-modal="true"
        aria-label={`${label} defect map`}
        onClick={(event) => event.stopPropagation()}
      >
        <div className="z-10 flex shrink-0 items-center justify-between gap-2 border-b border-border bg-popover px-3 py-2 text-sm">
          <span className="min-w-0 truncate font-medium text-popover-foreground" title={label}>
            {label}
          </span>
          <div className="flex shrink-0 items-center gap-2">
            {imageUrls.length > 0 ? (
              <span className="text-muted-foreground">{imageUrls.length} images</span>
            ) : null}
            {item?.url ? (
              <a
                href={item.url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 rounded-sm text-primary transition-colors hover:text-primary/80 focus:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                aria-label={`${label} URL 새 탭에서 열기`}
                title={item.url}
              >
                URL
                <ExternalLink className="h-3.5 w-3.5" />
              </a>
            ) : null}
            <button
              type="button"
              className="inline-flex h-7 w-7 items-center justify-center rounded-sm text-muted-foreground transition-colors hover:bg-muted hover:text-foreground focus:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
              aria-label={`${label} defect map 팝업 닫기`}
              onClick={() => onOpenChange(false)}
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>
        {imageUrls.length > 0 ? (
          <div className="overflow-y-auto p-3">
            <div className={`grid gap-3 ${isSingleImage ? "grid-cols-1" : "grid-cols-2"}`}>
              {imageUrls.map((src, imageIndex) => (
                <div
                  key={`${src}:${imageIndex}`}
                  className="block overflow-hidden rounded border border-border bg-background"
                  title={src}
                >
                  <img
                    src={src}
                    alt={`${label} preview ${imageIndex + 1}`}
                    className="aspect-square w-full object-contain"
                    loading="lazy"
                    referrerPolicy="no-referrer"
                  />
                </div>
              ))}
            </div>
          </div>
        ) : (
          <div className="flex h-56 flex-col items-center justify-center gap-3 px-4 text-center text-sm text-muted-foreground">
            <span>Preview image 없음</span>
            {item?.url ? (
              <a
                href={item.url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 rounded-sm text-primary transition-colors hover:text-primary/80 focus:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                aria-label={`${label} URL 새 탭에서 열기`}
                title={item.url}
              >
                URL
                <ExternalLink className="h-3.5 w-3.5" />
              </a>
            ) : null}
          </div>
        )}
      </div>
    </div>,
    document.body
  );
}

function DefectMapLinks({ maps }) {
  if (!Array.isArray(maps) || maps.length === 0) return null;

  return (
    <Field
      label="Defect Map"
      value={(
        <div className="flex flex-col gap-1">
          {maps.map((item, index) => (
            <DefectMapLink
              key={`${item.url}-${index}`}
              item={item}
              index={index}
            />
          ))}
        </div>
      )}
    />
  );
}

export default function EsopDetail({ log }) {
  return (
    <>
      <Field label="Log Type" value={log.logType} />
      <Field label="Sample Type" value={log.eventType} />
      <Field label="Lot ID" value={log.lotId} />
      <Field label="Status" value={log.status} />
      <Field label="Time" value={log.eventTime} />
      <Field label="Operator" value={log.operator} />
      <Field label="Line" value={log.lineId} />
      <Field label="EQP-CB" value={log.eqpCb} />
      <Field label="Comment" value={log.comment} fullWidth />
      <DefectMapLinks maps={log.defectMaps} />
    </>
  );
}
