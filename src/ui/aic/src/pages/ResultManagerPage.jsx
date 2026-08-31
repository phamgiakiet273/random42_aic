import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { useResultStore } from '../resultManager/store'
import {
  rowsFromCsv, rowSummary, buildSubmissionCsv, MAX_ROWS, frameBase,
} from '../resultManager/csv'
import ManagedRowCard from '../resultManager/ManagedRowCard'
import {
  ModeBar, UploadPanel, ManualEntryPanel, RangePanel, VqaPanel, MarksPanel,
} from '../resultManager/Panels'
import { downloadCsvFile } from '../utils/csv'
import { resultFrameUrl, resultVideoUrl, getFps } from '../api/resultManager'
import FrameDetailModal from '../components/FrameDetailModal'

function Section({ title, children }) {
  return (
    <div className="collapse collapse-arrow bg-base-100 shadow-sm">
      <input type="checkbox" defaultChecked />
      <div className="collapse-title text-sm font-medium py-2 min-h-0">{title}</div>
      <div className="collapse-content">{children}</div>
    </div>
  )
}

export default function ResultManagerPage() {
  const store = useResultStore()
  const { rows, mode, selected, thumbnailSize, filename } = store
  const [previewIndex, setPreviewIndex] = useState(null)
  const [dragging, setDragging] = useState(null)
  const [dragOver, setDragOver] = useState(null)
  const [notice, setNotice] = useState(null)
  const fileRef = useRef(null)

  const summary = rowSummary(rows, mode)
  const previewRow = previewIndex != null ? rows[previewIndex] : null

  const { data: previewFps } = useQuery({
    queryKey: ['fps', previewRow?.video_name],
    queryFn: () => getFps(previewRow.video_name),
    enabled: Boolean(previewRow?.video_name),
    retry: false,
  })

  // "M" marks the frame currently showing in the preview video.
  useEffect(() => {
    if (!previewRow) return
    const onKey = (e) => {
      if (e.key.toLowerCase() !== 'm') return
      const video = document.querySelector('dialog[open] video')
      if (!video) return
      const fps = previewFps || 25
      store.addMark(previewRow.video_name, Math.round(video.currentTime * fps))
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [previewRow, previewFps, store])

  async function handleUpload(file, insertIndex) {
    const text = await file.text()
    const { rows: parsed, detected } = rowsFromCsv(text, mode)
    if (!parsed.length) {
      setNotice({ err: true, text: 'No usable rows. Expected "<video_name>,<frame_idx>" with no header row.' })
      return
    }
    if (detected && detected !== mode) store.setMode(detected)
    store.insertRows(parsed, insertIndex)
    // Carry the uploaded name over to the download field, minus its extension
    // and any existing mode suffix (the suffix is re-applied on export).
    store.update({
      filename: file.name.replace(/\.csv$/i, '').replace(/-(kis|qa|trake)$/i, ''),
    })
    setNotice({ err: false, text: `Loaded ${parsed.length} rows${detected ? ` (detected ${detected.toUpperCase()})` : ''}.` })
  }

  function handleDownload() {
    if (!rows.length) return setNotice({ err: true, text: 'No rows to download.' })
    let out = rows
    if (rows.length > MAX_ROWS) {
      if (!window.confirm(`A submission CSV may hold at most ${MAX_ROWS} rows; this has ${rows.length}.\n\nExport only the first ${MAX_ROWS}?`)) return
      out = rows.slice(0, MAX_ROWS)
    }
    const { csv, problems } = buildSubmissionCsv(out, mode)
    if (problems.length) {
      const shown = problems.slice(0, 10).join('\n')
      const more = problems.length > 10 ? `\n...and ${problems.length - 10} more` : ''
      if (!window.confirm(`Found ${problems.length} issue(s):\n\n${shown}${more}\n\nDownload anyway?`)) return
    }
    const stem = (filename || 'query-1').replace(/\.csv$/i, '').replace(/-(kis|qa|trake)$/i, '')
    downloadCsvFile(`${stem}-${mode}.csv`, csv)
  }

  return (
    <main className="p-4 flex flex-col gap-3">
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <Link to="/" className="link link-hover text-sm">← Back to search</Link>
        <h1 className="text-xl font-semibold">Result Manager</h1>
      </div>

      <ModeBar />

      <div className="grid gap-3 lg:grid-cols-[22rem_1fr] items-start">
        <div className="flex flex-col gap-2">
          <Section title="Load CSV"><UploadPanel onUpload={handleUpload} /></Section>
          <Section title="Add rows manually"><ManualEntryPanel /></Section>
          <Section title="Add a frame range"><RangePanel /></Section>
          {mode === 'qa' && <Section title="Bulk answers"><VqaPanel /></Section>}
          {mode === 'trake' && <Section title="Marked frames"><MarksPanel /></Section>}
        </div>

        <div className="flex flex-col gap-3">
          <div className="flex items-center gap-2 flex-wrap">
            <span className={`text-sm ${summary.warn ? 'text-warning font-medium' : 'text-base-content/60'}`}>
              {summary.text}
            </span>
            <span className="flex-1" />
            <span className="text-xs text-base-content/50">{selected.size} selected</span>
            <button type="button" className="btn btn-xs" onClick={store.selectAll}>Select all</button>
            <button type="button" className="btn btn-xs" disabled={!selected.size}
              onClick={store.clearSelection}>Deselect</button>
            <button type="button" className="btn btn-xs btn-error" disabled={!selected.size}
              onClick={store.deleteSelected}>Delete selected</button>
          </div>

          <div className="flex items-center gap-3 flex-wrap">
            <label className="flex items-center gap-2 text-xs">
              Thumbnail
              <input type="range" min={100} max={320} step={20} className="range range-xs w-32"
                value={thumbnailSize}
                onChange={(e) => store.update({ thumbnailSize: Number(e.target.value) })} />
            </label>
            <span className="flex-1" />
            <input ref={fileRef} className="input input-sm input-bordered w-44"
              value={filename} onChange={(e) => store.update({ filename: e.target.value })} />
            <span className="text-xs text-base-content/50">-{mode}.csv</span>
            <button type="button" className="btn btn-sm btn-primary" onClick={handleDownload}>
              Download submission CSV
            </button>
          </div>

          {notice && (
            <div className={`alert py-2 text-sm ${notice.err ? 'alert-error' : 'alert-success'}`}>
              {notice.text}
            </div>
          )}

          {rows.length === 0 ? (
            <div className="hero bg-base-100 rounded-lg py-16">
              <div className="hero-content text-center text-base-content/60">
                <div>
                  <p className="text-lg font-medium">No rows yet</p>
                  <p className="text-sm">Upload a submission CSV, or add rows manually.</p>
                </div>
              </div>
            </div>
          ) : (
            <div className="flex flex-wrap gap-3">
              {rows.map((row, i) => (
                <ManagedRowCard
                  key={row.id} row={row} index={i} mode={mode} size={thumbnailSize}
                  selected={selected.has(i)}
                  onToggle={store.toggleSelected}
                  onPreview={setPreviewIndex}
                  onAnswer={(idx, answer) => store.updateRow(idx, { answer })}
                  onDragStart={setDragging}
                  onDragOver={setDragOver}
                  onDrop={(to) => { if (dragging != null && dragging !== to) store.moveRow(dragging, to) }}
                  onDragEnd={() => { setDragging(null); setDragOver(null) }}
                  isDragging={dragging === i}
                  isDragOver={dragOver === i && dragging !== i}
                />
              ))}
            </div>
          )}
        </div>
      </div>

      <FrameDetailModal
        record={previewRow && {
          video_name: previewRow.video_name,
          keyframe_id: frameBase(previewRow.frame_ids[0] || ''),
          fps: previewFps ?? null,
          score: 0,
          related_start_frame: frameBase(previewRow.frame_ids[0] || ''),
          related_end_frame: frameBase(previewRow.frame_ids.at(-1) || ''),
        }}
        urls={previewRow && {
          frame: resultFrameUrl(previewRow.video_name, previewRow.frame_ids[0]),
          video: resultVideoUrl(previewRow.video_name),
        }}
        onClose={() => setPreviewIndex(null)}
      />
    </main>
  )
}
