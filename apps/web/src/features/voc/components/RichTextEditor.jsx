import * as React from "react"
import Quill from "quill"

function normalizeEditorHtml(html) {
  if (!html || html === "<p><br></p>") return ""
  return html
}

export function RichTextEditor({
  id,
  value,
  onChange,
  placeholder,
  modules,
  formats,
  readOnly = false,
  className = "",
  ariaLabelledby,
  ariaLabel,
}) {
  const wrapperRef = React.useRef(null)
  const quillRef = React.useRef(null)
  const onChangeRef = React.useRef(onChange)
  const readOnlyRef = React.useRef(readOnly)
  const initialValueRef = React.useRef(value)
  const initialReadOnlyRef = React.useRef(readOnly)

  React.useEffect(() => {
    onChangeRef.current = onChange
  }, [onChange])

  React.useEffect(() => {
    readOnlyRef.current = readOnly
  }, [readOnly])

  React.useEffect(() => {
    const editorHost = wrapperRef.current
    const host = editorHost?.parentElement
    if (!editorHost || quillRef.current) return

    if (host) {
      host.querySelectorAll(".ql-toolbar").forEach((node) => node.remove())
    }
    editorHost.innerHTML = ""

    const quill = new Quill(editorHost, {
      theme: "snow",
      placeholder,
      modules,
      formats,
      readOnly: initialReadOnlyRef.current,
    })

    quillRef.current = quill

    const handleTextChange = (_delta, _old, source) => {
      if (source !== Quill.sources.USER) return
      if (!onChangeRef.current || readOnlyRef.current) return
      onChangeRef.current(normalizeEditorHtml(quill.root.innerHTML))
    }

    quill.on("text-change", handleTextChange)

    const initialValue = normalizeEditorHtml(initialValueRef.current || "")
    if (initialValue) {
      quill.clipboard.dangerouslyPasteHTML(initialValue, Quill.sources.SILENT)
    }
    quill.enable(!initialReadOnlyRef.current)

    return () => {
      quill.off("text-change", handleTextChange)
      if (host) {
        host.querySelectorAll(".ql-toolbar").forEach((node) => node.remove())
      }
      if (editorHost) {
        editorHost.innerHTML = ""
      }
      quillRef.current = null
    }
  }, [formats, modules, placeholder])

  React.useEffect(() => {
    const quill = quillRef.current
    if (!quill) return
    quill.enable(!readOnly)
  }, [readOnly])

  React.useEffect(() => {
    const quill = quillRef.current
    if (!quill) return

    const nextValue = normalizeEditorHtml(value || "")
    const currentValue = normalizeEditorHtml(quill.root.innerHTML)
    if (nextValue === currentValue) return

    quill.clipboard.dangerouslyPasteHTML(nextValue, Quill.sources.SILENT)
  }, [value])

  React.useEffect(() => {
    const quill = quillRef.current
    if (!quill?.root) return
    const root = quill.root

    if (id) {
      root.id = id
    } else {
      root.removeAttribute("id")
    }

    if (ariaLabelledby) {
      root.setAttribute("aria-labelledby", ariaLabelledby)
    } else {
      root.removeAttribute("aria-labelledby")
    }

    if (ariaLabel) {
      root.setAttribute("aria-label", ariaLabel)
    } else {
      root.removeAttribute("aria-label")
    }

    root.setAttribute("aria-readonly", readOnly ? "true" : "false")
  }, [id, ariaLabel, ariaLabelledby, readOnly])

  const handleWrapperPointerDown = (event) => {
    if (readOnlyRef.current) return
    const quill = quillRef.current
    if (!quill) return
    if (event.pointerType === "mouse" && event.button !== 0) return

    const target = event.target
    if (target && typeof target.closest === "function") {
      if (target.closest(".ql-toolbar")) return
      const clickedEditor = target.closest(".ql-editor")
      quill.focus()
      if (!clickedEditor) {
        quill.setSelection(quill.getLength(), 0, "silent")
      }
      return
    }

    quill.focus()
  }

  return (
    <div
      className={["voc-quill", className].filter(Boolean).join(" ")}
      onPointerDownCapture={handleWrapperPointerDown}
    >
      <div ref={wrapperRef} />
    </div>
  )
}
