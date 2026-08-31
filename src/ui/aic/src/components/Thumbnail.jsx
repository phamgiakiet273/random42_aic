import { useEffect, useRef } from 'react'
import { X, Newspaper, Images } from 'lucide-react'
import { useExcludedFramesStore } from '../stores/excludedFramesStore'
import { useSearchStore, recordKey } from '../stores/searchStore'
import { useSettingsStore } from '../stores/settingsStore'
import { useBaseSearchParams } from '../hooks/useBaseSearchParams'
import { UTILITY_FEATURES, utilityScrollParams } from '../api/search'
import { buildFrameUrl, videoStem } from '../api/media'
import { frameClassStyle } from '../utils/frameClass'
import { COLORS, placeholderThumbnail } from '../utils/placeholder'

export default function Thumbnail({ record, mediaConfig, index, onClick }) {
  const key = recordKey(record)
  const exclude = useExcludedFramesStore((s) => s.exclude)
  const skipFrames = useExcludedFramesStore((s) => s.skipFrames)
  const immediateRerun = useSettingsStore((s) => s.immediateRerun)
  const rerunWithSkips = useSearchStore((s) => s.rerunWithSkips)
  const execute = useSearchStore((s) => s.execute)
  const baseParams = useBaseSearchParams()

  const src = buildFrameUrl(mediaConfig, record)
  const label = videoStem(record.video_name)
  const fallback = placeholderThumbnail(label, COLORS[(index ?? 0) % COLORS.length])
  const transcript = Array.isArray(record.s2t) ? record.s2t.join(' ') : ''
  const cls = frameClassStyle(record.frame_class)
  const isOrigin = useSearchStore((s) => s.originKey) === key
  const cardRef = useRef(null)

  useEffect(() => {
    if (isOrigin) {
      cardRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' })
    }
  }, [isOrigin])

  async function handleExclude(e) {
    e.stopPropagation()
    exclude(record)
    if (immediateRerun) {
      try {
        await rerunWithSkips(skipFrames())
      } catch {
        /* surfaced by the store */
      }
    }
  }

  function runUtility(e, feature) {
    e.stopPropagation()
    execute(utilityScrollParams(record, feature, baseParams()), {
      originKey: key,
    }).catch(() => {})
  }

  return (
    <div
      ref={cardRef}
      className={`card bg-base-100 shadow-sm hover:shadow-md transition-shadow cursor-pointer ${
        isOrigin ? 'ring-2 ring-primary ring-offset-2 ring-offset-base-200' : ''
      }`}
      onClick={onClick}
      title={transcript || undefined}
    >
      <figure className="relative group">
        {index != null && (
          // Badge colour encodes frame_class (legacy drew it as a border).
          <span
            className={`badge border-0 absolute top-2 right-2 z-10 backdrop-blur-sm ${cls.badge}`}
            title={cls.label}
          >
            {index}
          </span>
        )}
        {record.chainId != null && (
          <span className="badge badge-primary badge-sm absolute bottom-2 left-2 z-10">
            event {record.chainPosition + 1}/{record.chainLength}
          </span>
        )}
        <img
          src={src || fallback}
          alt={label}
          loading="lazy"
          className="aspect-video w-full object-cover bg-base-200"
          onError={(e) => {
            if (e.target.src !== fallback) e.target.src = fallback
          }}
        />

        {/* Per-frame actions, mirroring the legacy card buttons. */}
        <div className="absolute bottom-2 right-2 z-10 flex gap-1 opacity-60 hover:opacity-100 focus-within:opacity-100 transition-opacity">
          <button
            type="button"
            className="btn btn-circle btn-xs"
            title="Browse this whole shot"
            onClick={(e) => runUtility(e, UTILITY_FEATURES.SHOT)}
          >
            <Newspaper size={12} />
          </button>
          <button
            type="button"
            className="btn btn-circle btn-xs"
            title="Find similar frames (duplicates of this frame)"
            onClick={(e) => runUtility(e, UTILITY_FEATURES.DUP)}
          >
            <Images size={12} />
          </button>
        </div>
      </figure>

      <div className="card-body p-3 gap-0.5">
        {/* Video and frame carry equal weight and share one row; the video
            timecode and the CLIP score were dropped as noise. */}
        <div className="flex items-center justify-between gap-2">
          <p className="text-sm font-medium truncate">
            <span>{label}</span>
            <span className="text-base-content/40">,</span>{' '}
            <span>{record.keyframe_id}</span>
          </p>
          <button
            type="button"
            className="btn btn-circle btn-xs shrink-0 jiggle-btn bg-red-300 hover:bg-red-400 border-none text-white"
            onClick={handleExclude}
            aria-label="Exclude this shot from results"
            title="Exclude this shot"
          >
            <X size={14} />
          </button>
        </div>
        {transcript && (
          <p className="text-[10px] leading-snug text-base-content/50 line-clamp-2">
            {transcript}
          </p>
        )}
      </div>
    </div>
  )
}
