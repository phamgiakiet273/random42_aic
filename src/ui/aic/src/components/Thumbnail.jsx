import { X } from 'lucide-react'
import { useExcludedFramesStore, frameKey } from '../stores/excludedFramesStore'
import { useSelectionStore } from '../stores/selectionStore'
import { cleanFrameName } from '../utils/frameName'

export default function Thumbnail({ video, index, onClick }) {
  const exclude = useExcludedFramesStore((s) => s.exclude)
  const selected = useSelectionStore((s) => s.selected.has(frameKey(video)))
  const toggleSelected = useSelectionStore((s) => s.toggle)

  return (
    <div
      className="card bg-base-100 shadow-sm hover:shadow-md transition-shadow cursor-pointer"
      onClick={onClick}
    >
      <figure className="relative">
        <input
          type="checkbox"
          className="checkbox checkbox-sm absolute top-2 left-2 z-10 bg-base-100"
          checked={selected}
          onClick={(e) => e.stopPropagation()}
          onChange={() => toggleSelected(frameKey(video))}
        />
        {index != null && (
          <span className="badge badge-neutral absolute top-2 right-2 z-10">{index}</span>
        )}
        <img
          src={video.thumbnail_url}
          alt={video.title}
          loading="lazy"
          className="aspect-video w-full object-cover"
        />
      </figure>
      <div className="card-body p-3 gap-0.5">
        <p className="text-sm font-medium truncate">{video.title}</p>
        <div className="flex items-center justify-between gap-2">
          <p className="text-xs text-base-content/60 truncate">
            {cleanFrameName(video.frame_name) || '—'} · {video.timestamp}
          </p>
          <button
            type="button"
            className="btn btn-circle btn-xs shrink-0 jiggle-btn bg-red-300 hover:bg-red-400 border-none text-white"
            onClick={(e) => {
              e.stopPropagation()
              exclude(video)
            }}
            aria-label="Exclude this frame"
          >
            <X size={14} />
          </button>
        </div>
      </div>
    </div>
  )
}
