import { useState } from 'react'
import { frameBase, frameLabel, MAX_ANSWER } from './csv'
import { resultFrameUrl } from '../api/resultManager'
import { COLORS, placeholderThumbnail } from '../utils/placeholder'

/** One TRAKE event, editable in place: reorder within the row (event order is
 *  what DRES scores), or drop it. Reusing the row's own drag-and-drop for this
 *  would conflict (it already reorders whole rows), so this is buttons, not a
 *  second nested drag context. */
function EventChip({ id, index, count, onMoveLeft, onMoveRight, onRemove }) {
  return (
    <span className="badge badge-xs gap-0.5 pl-1.5 pr-0.5 font-mono">
      {frameLabel(id)}
      <button
        type="button"
        className="disabled:opacity-30"
        disabled={index === 0}
        onClick={onMoveLeft}
        aria-label={`Move event ${index + 1} earlier`}
      >
        ‹
      </button>
      <button
        type="button"
        className="disabled:opacity-30"
        disabled={index === count - 1}
        onClick={onMoveRight}
        aria-label={`Move event ${index + 1} later`}
      >
        ›
      </button>
      <button type="button" onClick={onRemove} aria-label={`Remove event ${index + 1}`}>
        ×
      </button>
    </span>
  )
}

export default function ManagedRowCard({
  row, index, mode, size, selected, onToggle, onPreview, onAnswer, onUpdateFrames,
  onDragStart, onDragOver, onDrop, onDragEnd, isDragging, isDragOver,
}) {
  const [newFrame, setNewFrame] = useState('')
  const first = row.frame_ids[0] || ''
  const src = resultFrameUrl(row.video_name, first)
  const fallback = placeholderThumbnail(row.video_name || '?', COLORS[index % COLORS.length])
  const overLong = (row.answer || '').trim().length > MAX_ANSWER

  function moveEvent(i, delta) {
    const frames = [...row.frame_ids]
    const j = i + delta
    if (j < 0 || j >= frames.length) return
    ;[frames[i], frames[j]] = [frames[j], frames[i]]
    onUpdateFrames(index, frames)
  }
  function removeEvent(i) {
    onUpdateFrames(index, row.frame_ids.filter((_, k) => k !== i))
  }
  function addEvent() {
    const value = frameBase(newFrame)
    if (!value) return
    onUpdateFrames(index, [...row.frame_ids, value])
    setNewFrame('')
  }

  return (
    <div
      draggable
      onDragStart={() => onDragStart(index)}
      onDragOver={(e) => { e.preventDefault(); onDragOver(index) }}
      onDrop={() => onDrop(index)}
      onDragEnd={onDragEnd}
      className={`card bg-base-100 shadow-sm transition-all ${
        isDragging ? 'opacity-40 scale-95'
        : isDragOver ? 'ring-2 ring-primary scale-105'
        : selected ? 'ring-2 ring-secondary' : 'hover:shadow-md'
      }`}
      style={{ width: size }}
    >
      <figure className="relative cursor-pointer" onClick={() => onPreview(index)}>
        <input
          type="checkbox"
          className="checkbox checkbox-sm absolute top-2 left-2 z-10 bg-base-100"
          checked={selected}
          onClick={(e) => { e.stopPropagation(); onToggle(index, e.shiftKey) }}
          onChange={() => {}}
        />
        <span className="badge badge-neutral badge-sm absolute top-2 right-2 z-10">{index + 1}</span>
        <img
          src={src || fallback}
          alt={row.video_name}
          loading="lazy"
          className="w-full aspect-video object-cover bg-base-200"
          onError={(e) => { if (e.target.src !== fallback) e.target.src = fallback }}
        />
      </figure>
      <div className="card-body p-2 gap-1">
        <p className="text-xs font-medium truncate" title={row.video_name}>{row.video_name}</p>
        {mode === 'trake' ? (
          <div className="flex flex-col gap-1">
            <div className="flex flex-wrap gap-1">
              {row.frame_ids.map((id, i) => (
                <EventChip
                  key={`${i}-${id}`}
                  id={id}
                  index={i}
                  count={row.frame_ids.length}
                  onMoveLeft={() => moveEvent(i, -1)}
                  onMoveRight={() => moveEvent(i, 1)}
                  onRemove={() => removeEvent(i)}
                />
              ))}
            </div>
            <div className="flex gap-1">
              <input
                type="text"
                inputMode="numeric"
                placeholder="add frame…"
                className="input input-xs input-bordered flex-1 min-w-0 font-mono"
                value={newFrame}
                onChange={(e) => setNewFrame(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addEvent() } }}
              />
              <button type="button" className="btn btn-xs" onClick={addEvent}>+</button>
            </div>
          </div>
        ) : (
          <p className="text-[10px] text-base-content/60">{frameLabel(first)}</p>
        )}
        {mode === 'qa' && (
          <input
            type="text"
            maxLength={MAX_ANSWER}
            placeholder="answer…"
            title={`Q&A answer (max ${MAX_ANSWER} characters)`}
            className={`input input-xs w-full ${overLong ? 'input-error' : 'input-bordered'}`}
            value={row.answer}
            onChange={(e) => onAnswer(index, e.target.value)}
          />
        )}
      </div>
    </div>
  )
}
