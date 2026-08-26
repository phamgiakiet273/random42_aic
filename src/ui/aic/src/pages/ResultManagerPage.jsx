import { useState, useRef } from 'react'
import Papa from 'papaparse'
import { Link } from 'react-router-dom'
import { toResultCsv, downloadCsvFile } from '../utils/csv'
import { COLORS, placeholderThumbnail } from '../utils/placeholder'
import { buildThumbnailUrl } from '../utils/media'
import ResultCard from '../components/ResultCard'
import FrameDetailModal from '../components/FrameDetailModal'

export default function ResultManagerPage() {
  const [rows, setRows] = useState([])
  const [selected, setSelected] = useState(new Set())
  const [draggingIndex, setDraggingIndex] = useState(null)
  const [overIndex, setOverIndex] = useState(null)
  const [previewIndex, setPreviewIndex] = useState(null)
  const dragIndex = useRef(null)

  const handleFileUpload = (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    const reader = new FileReader()
    reader.onload = () => {
      const parsed = Papa.parse(reader.result, { skipEmptyLines: true })
      const newRows = parsed.data.map(([video_id, keyframe_id], i) => ({
        id: i,
        video_id,
        keyframe_id,
      }))
      setRows(newRows)
      setSelected(new Set())
    }
    reader.readAsText(file)
    e.target.value = ''
  }

  const toggleSelected = (id) => {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const handleDeleteSelected = () => {
    setRows((prev) => prev.filter((r) => !selected.has(r.id)))
    setSelected(new Set())
  }

  const handleDragStart = (index) => {
    dragIndex.current = index
    setDraggingIndex(index)
  }

  const handleDragOver = (index) => {
    if (index !== dragIndex.current) setOverIndex(index)
  }

  const handleDrop = (index) => {
    setRows((prev) => {
      const next = [...prev]
      const [moved] = next.splice(dragIndex.current, 1)
      next.splice(index, 0, moved)
      return next
    })
    dragIndex.current = null
    setDraggingIndex(null)
    setOverIndex(null)
  }

  const handleDragEnd = () => {
    dragIndex.current = null
    setDraggingIndex(null)
    setOverIndex(null)
  }

  const handleDownload = () => {
    downloadCsvFile('adjusted_result.csv', toResultCsv(rows))
  }

  const previewRow = previewIndex != null ? rows[previewIndex] : null
  const previewVideo = previewRow && {
    id: previewRow.id,
    video_id: previewRow.video_id || 'Unknown Video',
    title: previewRow.video_id || 'Invalid Keyframe',
    keyframe_id: previewRow.keyframe_id,
    timestamp: '',
    thumbnail_url:
      buildThumbnailUrl(previewRow.video_id, previewRow.keyframe_id) ||
      placeholderThumbnail(previewRow.video_id || 'Unknown Video', COLORS[previewIndex % COLORS.length]),
  }

  return (
    <main className="p-4 flex flex-col gap-4">
      <Link to="/" className="link link-hover text-sm">
        ← Back
      </Link>
      <h1 className="text-xl font-semibold">Result Manager</h1>

      <div className="flex flex-wrap items-center gap-2">
        <input
          type="file"
          accept=".csv"
          onChange={handleFileUpload}
          className="file-input file-input-sm"
        />
        <button
          type="button"
          className="btn btn-sm btn-error"
          disabled={selected.size === 0}
          onClick={handleDeleteSelected}
        >
          Delete Selected
        </button>
        <button
          type="button"
          className="btn btn-sm btn-primary ml-auto"
          disabled={rows.length === 0}
          onClick={handleDownload}
        >
          Download Result
        </button>
      </div>

      {rows.length === 0 ? (
        <p className="text-sm text-base-content/60">Upload a CSV to get started.</p>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
          {rows.map((row, index) => (
            <ResultCard
              key={row.id}
              row={row}
              index={index}
              selected={selected.has(row.id)}
              onToggleSelected={toggleSelected}
              onDragStart={handleDragStart}
              onDragOver={handleDragOver}
              onDrop={handleDrop}
              onDragEnd={handleDragEnd}
              isDragging={draggingIndex === index}
              isDragOver={overIndex === index}
              onClick={() => setPreviewIndex(index)}
            />
          ))}
        </div>
      )}

      <FrameDetailModal video={previewVideo} onClose={() => setPreviewIndex(null)} />
    </main>
  )
}
