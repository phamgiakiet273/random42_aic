import { useState } from 'react'
import { useResultStore } from './store'
import { MODES, MODE_HINT, frameLabel } from './csv'

/** Where new rows land: start, end, or a 1-based position. */
function usePosition(rowCount) {
  const [where, setWhere] = useState('end')
  const [index, setIndex] = useState('1')
  const resolve = () =>
    where === 'start' ? 0
    : where === 'end' ? rowCount
    : Math.max(0, Math.min(parseInt(index, 10) - 1 || 0, rowCount))
  return { where, setWhere, index, setIndex, resolve }
}

function PositionPicker({ pos }) {
  return (
    <div className="flex items-center gap-2 flex-wrap">
      {['start', 'end', 'custom'].map((v) => (
        <label key={v} className="label cursor-pointer gap-1 py-0">
          <input
            type="radio" className="radio radio-xs" checked={pos.where === v}
            onChange={() => pos.setWhere(v)}
          />
          <span className="label-text text-xs capitalize">{v}</span>
        </label>
      ))}
      <input
        type="number" min={1} className="input input-xs input-bordered w-20"
        disabled={pos.where !== 'custom'} value={pos.index}
        onChange={(e) => pos.setIndex(e.target.value)}
      />
    </div>
  )
}

export function ModeBar() {
  const { mode, setMode } = useResultStore()
  return (
    <div className="flex items-center gap-3 flex-wrap">
      <div className="join">
        {MODES.map((m) => (
          <button
            key={m} type="button"
            className={`btn btn-sm join-item ${mode === m ? 'btn-active btn-primary' : ''}`}
            onClick={() => setMode(m)}
          >
            {m.toUpperCase()}
          </button>
        ))}
      </div>
      <span className="text-xs text-base-content/60 font-mono">{MODE_HINT[mode]}</span>
    </div>
  )
}

export function UploadPanel({ onUpload }) {
  const rows = useResultStore((s) => s.rows)
  const pos = usePosition(rows.length)
  return (
    <div className="flex items-center gap-2 flex-wrap">
      <input
        type="file" accept=".csv,text/csv"
        className="file-input file-input-bordered file-input-sm"
        onChange={(e) => {
          const file = e.target.files?.[0]
          if (file) onUpload(file, pos.resolve())
          e.target.value = ''
        }}
      />
      <span className="text-xs text-base-content/50">insert at</span>
      <PositionPicker pos={pos} />
    </div>
  )
}

export function ManualEntryPanel() {
  const { rows, addManual, mode } = useResultStore()
  const pos = usePosition(rows.length)
  const [video, setVideo] = useState('')
  const [frames, setFrames] = useState('')
  const [error, setError] = useState(null)

  const submit = () => {
    setError(null)
    if (!video.trim() || !frames.trim()) return setError('Video name and frame ID are required')
    const res = addManual({ videoName: video.trim(), frameInput: frames, insertIndex: pos.resolve() })
    if (!res.ok) return setError(res.error)
    setFrames('')
  }
  return (
    <div className="flex flex-col gap-2">
      <div className="flex gap-2 flex-wrap">
        <input className="input input-sm input-bordered w-36" placeholder="L21_V001"
          value={video} onChange={(e) => setVideo(e.target.value)} />
        <input className="input input-sm input-bordered flex-1 min-w-40"
          placeholder={mode === 'trake' ? '1200, 1850, 2100' : '1200'}
          value={frames} onChange={(e) => setFrames(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && submit()} />
        <button type="button" className="btn btn-sm btn-primary" onClick={submit}>Add</button>
      </div>
      <PositionPicker pos={pos} />
      {error && <p className="text-xs text-error">{error}</p>}
    </div>
  )
}

export function RangePanel() {
  const { rows, addRange, mode } = useResultStore()
  const pos = usePosition(rows.length)
  const [video, setVideo] = useState('')
  const [start, setStart] = useState('')
  const [end, setEnd] = useState('')
  const [interval, setIntervalValue] = useState('1')
  const [msg, setMsg] = useState(null)

  const submit = () => {
    setMsg(null)
    const s = parseInt(start, 10), e = parseInt(end, 10), iv = parseInt(interval, 10) || 1
    if (!video.trim()) return setMsg({ err: true, text: 'Video name is required' })
    if (!Number.isFinite(s) || !Number.isFinite(e)) return setMsg({ err: true, text: 'Start and end must be numbers' })
    if (s > e) return setMsg({ err: true, text: 'Start must be <= end' })
    if (iv < 1) return setMsg({ err: true, text: 'Interval must be at least 1' })
    const n = addRange({ videoName: video.trim(), start: s, end: e, interval: iv, insertIndex: pos.resolve() })
    setMsg({
      err: false,
      text: mode === 'trake'
        ? `Added 1 TRAKE row with ${n} events`
        : `Added ${n} rows (${s}–${e}, interval ${iv})`,
    })
  }
  return (
    <div className="flex flex-col gap-2">
      <div className="flex gap-2 flex-wrap">
        <input className="input input-sm input-bordered w-32" placeholder="L21_V001"
          value={video} onChange={(e) => setVideo(e.target.value)} />
        <input className="input input-sm input-bordered w-24" placeholder="start"
          value={start} onChange={(e) => setStart(e.target.value)} />
        <input className="input input-sm input-bordered w-24" placeholder="end"
          value={end} onChange={(e) => setEnd(e.target.value)} />
        <input className="input input-sm input-bordered w-20" placeholder="every"
          value={interval} onChange={(e) => setIntervalValue(e.target.value)} />
        <button type="button" className="btn btn-sm btn-primary" onClick={submit}>Add range</button>
      </div>
      <PositionPicker pos={pos} />
      {msg && <p className={`text-xs ${msg.err ? 'text-error' : 'text-success'}`}>{msg.text}</p>}
    </div>
  )
}

export function VqaPanel() {
  const { mode, rows, applyAnswers } = useResultStore()
  const [advanced, setAdvanced] = useState(false)
  const [single, setSingle] = useState('')
  const [bands, setBands] = useState({ row1: '', row2_5: '', row6_20: '', row21_50: '', row51_end: '' })
  const [msg, setMsg] = useState(null)

  if (mode !== 'qa') return null
  const band = (key, label) => (
    <label key={key} className="flex items-center gap-2">
      <span className="text-xs w-20 text-base-content/60">{label}</span>
      <input className="input input-xs input-bordered flex-1" maxLength={100}
        value={bands[key]} onChange={(e) => setBands({ ...bands, [key]: e.target.value })} />
    </label>
  )
  const apply = () => {
    setMsg(null)
    if (!rows.length) return setMsg('No rows to fill.')
    if (!advanced && !single.trim()) return setMsg('Enter an answer to apply.')
    applyAnswers(advanced ? { bands } : { single: single.trim() })
    setMsg(advanced ? 'Applied by row band.' : `Applied to all ${rows.length} rows.`)
  }
  return (
    <div className="flex flex-col gap-2">
      <label className="label cursor-pointer justify-start gap-2 py-0">
        <input type="checkbox" className="checkbox checkbox-xs" checked={advanced}
          onChange={(e) => setAdvanced(e.target.checked)} />
        <span className="label-text text-xs">Different answers per row band</span>
      </label>
      {advanced ? (
        <div className="flex flex-col gap-1">
          {band('row1', 'row 1')}
          {band('row2_5', 'rows 2–5')}
          {band('row6_20', 'rows 6–20')}
          {band('row21_50', 'rows 21–50')}
          {band('row51_end', 'rows 51+')}
          <p className="text-[10px] text-base-content/50">An empty band leaves those rows unchanged.</p>
        </div>
      ) : (
        <input className="input input-sm input-bordered w-full" maxLength={100}
          placeholder="answer applied to every row" value={single}
          onChange={(e) => setSingle(e.target.value)} />
      )}
      <button type="button" className="btn btn-sm" onClick={apply}>Apply answers</button>
      {msg && <p className="text-xs text-base-content/60">{msg}</p>}
    </div>
  )
}

export function MarksPanel() {
  const { marks, markVideo, removeMark, clearMarks, addRowFromMarks, rows } = useResultStore()
  if (!marks.length) {
    return (
      <p className="text-xs text-base-content/50">
        Open a row, then press <kbd className="kbd kbd-xs">M</kbd> while the video plays to mark
        the current frame. Marks become one TRAKE row.
      </p>
    )
  }
  return (
    <div className="flex flex-col gap-2">
      <p className="text-xs text-base-content/60">{markVideo} — {marks.length} marked</p>
      <ul className="flex flex-wrap gap-1">
        {marks.map((f) => (
          <li key={f} className="badge badge-sm gap-1">
            {frameLabel(f)}
            <button type="button" onClick={() => removeMark(f)} aria-label={`Remove ${f}`}>✕</button>
          </li>
        ))}
      </ul>
      <div className="flex gap-2">
        <button type="button" className="btn btn-xs btn-primary"
          onClick={() => addRowFromMarks(rows.length)}>Add as TRAKE row</button>
        <button type="button" className="btn btn-xs" onClick={clearMarks}>Clear</button>
      </div>
    </div>
  )
}
