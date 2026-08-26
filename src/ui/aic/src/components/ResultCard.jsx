export default function ResultCard({
  row,
  index,
  selected,
  onToggleSelected,
  onDragStart,
  onDragOver,
  onDrop,
  onDragEnd,
  isDragging,
  isDragOver,
}) {
  return (
    <div
      draggable
      onDragStart={() => onDragStart(index)}
      onDragOver={(e) => {
        e.preventDefault()
        onDragOver(index)
      }}
      onDrop={() => onDrop(index)}
      onDragEnd={onDragEnd}
      className={`card bg-base-100 shadow-sm transition-all duration-150 cursor-move relative ${
        isDragging
          ? 'opacity-40 scale-95'
          : isDragOver
            ? 'ring-2 ring-primary ring-offset-2 scale-105'
            : 'hover:shadow-md'
      }`}
    >
      <input
        type="checkbox"
        className="checkbox checkbox-sm absolute top-2 left-2 z-10 bg-base-100"
        checked={selected}
        onClick={(e) => e.stopPropagation()}
        onChange={() => onToggleSelected(row.id)}
      />
      <span className="badge badge-neutral absolute top-2 right-2 z-10">{index + 1}</span>
      <figure className="aspect-video w-full bg-base-300 flex items-center justify-center text-xs text-base-content/40">
        No preview
      </figure>
      <div className="card-body p-3 gap-0.5">
        <p className="text-sm font-medium truncate">{row.video_id || 'Unknown Video'}</p>
        <p className="text-xs text-base-content/60 truncate">{row.keyframe_id || '—'}</p>
      </div>
    </div>
  )
}
