import { useState } from 'react'
import { useSelectionStore } from '../stores/selectionStore'
import { useExcludedFramesStore, frameKey } from '../stores/excludedFramesStore'

export default function BulkActions({ records }) {
  const selected = useSelectionStore((s) => s.selected)
  const selectMany = useSelectionStore((s) => s.selectMany)
  const clearSelection = useSelectionStore((s) => s.clear)
  const exclude = useExcludedFramesStore((s) => s.exclude)

  const [rangeFrom, setRangeFrom] = useState('')
  const [rangeTo, setRangeTo] = useState('')

  const handleSelectAll = () => {
    selectMany(records.map((r) => frameKey(r)))
  }

  const handleSelectRange = () => {
    const from = parseInt(rangeFrom, 10)
    const to = parseInt(rangeTo, 10)
    if (Number.isNaN(from) || Number.isNaN(to)) return
    const lo = Math.max(1, Math.min(from, to))
    const hi = Math.min(records.length, Math.max(from, to))
    selectMany(records.slice(lo - 1, hi).map((r) => frameKey(r)))
  }

  const handleDeleteSelected = () => {
    records.forEach((r) => {
      if (selected.has(frameKey(r))) exclude(r)
    })
    clearSelection()
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="text-xs text-base-content/60 w-24">{selected.size} selected</span>
      <button type="button" className="btn btn-xs" onClick={handleSelectAll}>
        Select All
      </button>
      <button
        type="button"
        className="btn btn-xs"
        disabled={selected.size === 0}
        onClick={clearSelection}
      >
        Clear
      </button>
      <button
        type="button"
        className="btn btn-xs btn-error"
        disabled={selected.size === 0}
        onClick={handleDeleteSelected}
      >
        Delete Selected
      </button>
      <div className="flex items-center gap-1">
        <input
          type="number"
          min={1}
          placeholder="From"
          value={rangeFrom}
          onChange={(e) => setRangeFrom(e.target.value)}
          className="input input-xs w-16"
        />
        <span className="text-xs text-base-content/60">-</span>
        <input
          type="number"
          min={1}
          placeholder="To"
          value={rangeTo}
          onChange={(e) => setRangeTo(e.target.value)}
          className="input input-xs w-16"
        />
        <button type="button" className="btn btn-xs" onClick={handleSelectRange}>
          Select Range
        </button>
      </div>
    </div>
  )
}
