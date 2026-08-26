import { useState, useRef } from 'react'
import Papa from 'papaparse'
import { Link } from 'react-router-dom'
import { toResultCsv, downloadCsvFile } from '../utils/csv'

export default function ResultManagerPage() {
  const [rows, setRows] = useState([])
  const [selected, setSelected] = useState(new Set())
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
  }

  const handleDrop = (index) => {
    setRows((prev) => {
      const next = [...prev]
      const [moved] = next.splice(dragIndex.current, 1)
      next.splice(index, 0, moved)
      return next
    })
    dragIndex.current = null
  }

  const handleDownload = () => {
    downloadCsvFile('adjusted_result.csv', toResultCsv(rows))
  }

  return (
    <main className="p-4 flex flex-col gap-4 max-w-3xl mx-auto">
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
        <ul className="flex flex-col gap-1">
          {rows.map((row, index) => (
            <li
              key={row.id}
              draggable
              onDragStart={() => handleDragStart(index)}
              onDragOver={(e) => e.preventDefault()}
              onDrop={() => handleDrop(index)}
              className="flex items-center gap-3 bg-base-100 rounded p-2 shadow-sm cursor-move"
            >
              <span className="text-xs text-base-content/50 w-8 text-right">{index + 1}</span>
              <input
                type="checkbox"
                className="checkbox checkbox-sm"
                checked={selected.has(row.id)}
                onChange={() => toggleSelected(row.id)}
              />
              <span className="font-mono text-sm">{row.video_id}</span>
              <span className="font-mono text-sm text-base-content/60">{row.keyframe_id}</span>
            </li>
          ))}
        </ul>
      )}
    </main>
  )
}
