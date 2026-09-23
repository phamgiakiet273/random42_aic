import { ListOrdered } from 'lucide-react'
import Thumbnail from './Thumbnail'
import { useSettingsStore } from '../stores/settingsStore'
import { useSubmissionStore } from '../stores/submissionStore'

/** One temporal result: a row whose columns are its matched events, in order.
 *  Flattening chains into the normal grid loses that sequence. */
export default function TemporalChainRow({ chain, rank, mediaConfig, onSelect }) {
  const thumbnailSize = useSettingsStore((s) => s.thumbnailSize)
  const loadTrakeChain = useSubmissionStore((s) => s.loadTrakeChain)
  const first = chain[0] || {}
  const videoName = String(first.video_name ?? '').split('.')[0]
  const total = chain.reduce((sum, frame) => sum + (Number(frame.score) || 0), 0)

  // Temporal search already returns exactly a TRAKE answer's shape (ordered
  // events, one video) — this skips marking each frame by hand.
  function useAsTrake() {
    const frameIds = chain.map((frame) => parseInt(frame.keyframe_id, 10))
    loadTrakeChain(videoName, frameIds)
  }

  return (
    <div className="card bg-base-100 shadow-sm">
      <div className="card-body p-3 gap-2">
        <div className="flex items-baseline justify-between gap-2">
          <span className="text-sm font-medium">
            <span className="badge badge-neutral badge-sm mr-2">{rank}</span>
            {videoName}
          </span>
          <span className="flex items-center gap-2">
            <span className="text-xs text-base-content/50">
              {chain.length} event{chain.length === 1 ? '' : 's'} · Σ {total.toFixed(3)}
            </span>
            <button
              type="button"
              className="btn btn-xs btn-outline gap-1"
              title="Load this chain as the TRAKE sequence in the submission bar"
              onClick={useAsTrake}
            >
              <ListOrdered size={12} /> Use as TRAKE
            </button>
          </span>
        </div>
        {/* Fixed-width columns at the configured thumbnail size: stretching a
            2-event chain across the full row blew the frames up far larger than
            the grid's. Long chains scroll sideways instead. */}
        <div
          className="grid gap-3 overflow-x-auto pb-1 justify-center"
          style={{ gridTemplateColumns: `repeat(${chain.length}, ${thumbnailSize}px)` }}
        >
          {chain.map((frame, i) => (
            <Thumbnail
              key={`${frame.key}:${i}`}
              record={frame}
              mediaConfig={mediaConfig}
              index={i + 1}
              onClick={() => onSelect(frame)}
            />
          ))}
        </div>
      </div>
    </div>
  )
}
