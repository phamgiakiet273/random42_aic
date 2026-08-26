import { X } from 'lucide-react'
import { useExcludedFramesStore } from '../stores/excludedFramesStore'
import { cleanFrameName } from '../utils/frameName'

export default function Thumbnail({ video, onClick }) {
  const exclude = useExcludedFramesStore((s) => s.exclude)

  return (
    <div
      className="card bg-base-100 shadow-sm hover:shadow-md transition-shadow cursor-pointer"
      onClick={onClick}
    >
      <figure>
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
