import { frameLabel, MAX_ANSWER } from './csv'
import { resultFrameUrl } from '../api/resultManager'
import { COLORS, placeholderThumbnail } from '../utils/placeholder'

export default function ManagedRowCard({
  row, index, mode, size, selected, onToggle, onPreview, onAnswer,
  onDragStart, onDragOver, onDrop, onDragEnd, isDragging, isDragOver,
}) {
  const first = row.frame_ids[0] || ''
  const src = resultFrameUrl(row.video_name, first)
  const fallback = placeholderThumbnail(row.video_name || '?', COLORS[index % COLORS.length])
  const overLong = (row.answer || '').trim().length > MAX_ANSWER

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
          <p className="text-[10px] text-base-content/60 truncate" title={row.frame_ids.join(', ')}>
            {row.frame_ids.length} events: {row.frame_ids.map(frameLabel).join(', ')}
          </p>
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
