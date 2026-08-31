import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { getNeighboringFrames } from '../api/search'
import {
  buildFrameUrl,
  buildVideoUrl,
  frameToSeconds,
  formatTimecode,
  videoStem,
} from '../api/media'
import { useTrakeStore } from '../stores/trakeStore'
import { useSettingsStore } from '../stores/settingsStore'

// `urls` overrides the media-config-derived URLs. The result manager needs it:
// a row read from a submission CSV has no batch, so its media has to be
// resolved by the result_manager service instead of composed in the browser.
export default function FrameDetailModal({ record, mediaConfig, urls, onClose }) {
  const dialogRef = useRef(null)
  const videoRef = useRef(null)
  const currentNeighborRef = useRef(null)
  const [currentFrame, setCurrentFrame] = useState(null)
  const neighborCount = useSettingsStore((s) => s.neighborFrameCount)

  const trakeVideoId = useTrakeStore((s) => s.videoId)
  const trakeFrames = useTrakeStore((s) => s.frames)
  const markFrame = useTrakeStore((s) => s.markFrame)
  const removeFrame = useTrakeStore((s) => s.removeFrame)

  const videoName = record ? videoStem(record.video_name) : null
  // Do NOT silently fall back to 25. fps varies across the dataset (950 videos
  // at 25, 359 at 30, 30 at 29.97, plus a drifting tail), so guessing produces
  // a timestamp that looks right and is not. When it is genuinely unknown the
  // UI says so instead.
  const rawFps = Number(record?.fps)
  const fpsKnown = Number.isFinite(rawFps) && rawFps > 0
  const fps = fpsKnown ? rawFps : 25
  const startSeconds = record ? frameToSeconds(record.keyframe_id, fps) : null
  const videoUrl = urls?.video ?? buildVideoUrl(mediaConfig, record)
  const frameUrl = urls?.frame ?? buildFrameUrl(mediaConfig, record)

  // The util service may not be running; a failure here must not break the modal.
  const { data: neighbors } = useQuery({
    queryKey: ['neighbors', videoName, record?.keyframe_id, neighborCount],
    queryFn: () => getNeighboringFrames(videoName, record.keyframe_id, neighborCount),
    enabled: Boolean(record && videoName && !urls),
    retry: false,
  })

  useEffect(() => {
    const dialog = dialogRef.current
    if (!dialog) return
    if (record) dialog.showModal()
    else dialog.close()
    setCurrentFrame(record ? Number(record.keyframe_id) : null)
  }, [record])

  // Seek to the frame the user clicked, then track playback position as a frame
  // number (doc comment [j]: frame / fps = seconds, and back again).
  useEffect(() => {
    const el = videoRef.current
    if (!el || startSeconds == null) return
    const seek = () => {
      el.currentTime = startSeconds
    }
    const track = () => setCurrentFrame(Math.floor(el.currentTime * fps))
    el.addEventListener('loadedmetadata', seek)
    el.addEventListener('timeupdate', track)
    return () => {
      el.removeEventListener('loadedmetadata', seek)
      el.removeEventListener('timeupdate', track)
    }
  }, [videoUrl, startSeconds, fps])

  const nudge = useCallback(
    (deltaSeconds) => {
      const el = videoRef.current
      if (!el) return
      el.currentTime = Math.max(0, Math.min(el.duration || Infinity, el.currentTime + deltaSeconds))
      setCurrentFrame(Math.floor(el.currentTime * fps))
    },
    [fps],
  )

  useEffect(() => {
    const dialog = dialogRef.current
    if (!dialog || !record) return
    const onKeyDown = (e) => {
      if (e.key === 'ArrowLeft') {
        e.preventDefault()
        nudge(e.shiftKey ? -1 : -1 / fps)
      } else if (e.key === 'ArrowRight') {
        e.preventDefault()
        nudge(e.shiftKey ? 1 : 1 / fps)
      }
    }
    dialog.addEventListener('keydown', onKeyDown)
    return () => dialog.removeEventListener('keydown', onKeyDown)
  }, [record, fps, nudge])

  const markedHere = trakeVideoId === videoName ? trakeFrames : []
  const transcript = Array.isArray(record?.s2t) ? record.s2t.join(' ') : ''

  // The clicked frame sits between its neighbours rather than being absent, so
  // the strip reads as a timeline and the current position is visible.
  const neighborStrip = useMemo(() => {
    const prev = neighbors?.prev_frames || []
    const next = neighbors?.next_frames || []
    return [
      ...prev.map((path) => ({ path, current: false })),
      { path: frameUrl, current: true },
      ...next.map((path) => ({ path, current: false })),
    ]
  }, [neighbors, frameUrl])

  // Centre the current frame instead of leaving the user to scroll to it
  // (the legacy UI did this with scrollIntoView block:'center').
  const centreCurrentNeighbor = useCallback((smooth = true) => {
    const el = currentNeighborRef.current
    const strip = el?.parentElement
    if (!el || !strip) return
    // Compute the offset directly rather than relying on scrollIntoView: it
    // measures whatever layout exists at call time, which with lazily-loaded
    // images is often not the final one.
    strip.scrollTo({
      left: el.offsetLeft - (strip.clientWidth - el.clientWidth) / 2,
      behavior: smooth ? 'smooth' : 'auto',
    })
  }, [])

  useEffect(() => {
    if (neighborStrip.length <= 1) return
    centreCurrentNeighbor(false)
  }, [neighborStrip, centreCurrentNeighbor])

  return (
    <dialog ref={dialogRef} className="modal" onClose={onClose}>
      {record && (
        <div className="modal-box max-w-3xl">
          <h3 className="font-semibold text-lg">{videoName}</h3>
          <p className="text-sm text-base-content/60 mb-3">
            frame {record.keyframe_id} · {formatTimecode(startSeconds)} ·{' '}
            {fpsKnown ? `${fps} fps` : 'fps unknown, assuming 25'}
            {record.score > 0 && <> · score {record.score.toFixed(4)}</>}
            {' · '}shot {record.related_start_frame}–{record.related_end_frame}
          </p>

          {videoUrl ? (
            <video
              key={videoUrl}
              ref={videoRef}
              src={startSeconds != null ? `${videoUrl}#t=${startSeconds}` : videoUrl}
              poster={frameUrl || undefined}
              controls
              autoPlay
              className="w-full rounded-lg aspect-video bg-black"
            />
          ) : (
            <img
              src={frameUrl}
              alt={videoName}
              className="w-full rounded-lg aspect-video object-contain bg-black"
            />
          )}

          <div className="flex items-center justify-center gap-3 mt-3 text-sm flex-wrap">
            <span>
              <strong>Current frame:</strong> {currentFrame ?? '—'}
            </span>
            <span className="text-base-content/50">
              {formatTimecode((currentFrame ?? 0) / fps)}
            </span>
            <div className="join">
              <button type="button" className="btn btn-xs join-item" onClick={() => nudge(-1)}>« 1s</button>
              <button type="button" className="btn btn-xs join-item" onClick={() => nudge(-1 / fps)}>‹ 1f</button>
              <button type="button" className="btn btn-xs join-item" onClick={() => nudge(1 / fps)}>1f ›</button>
              <button type="button" className="btn btn-xs join-item" onClick={() => nudge(1)}>1s »</button>
            </div>
            {frameUrl && (
              <a href={frameUrl} target="_blank" rel="noreferrer" className="btn btn-xs btn-ghost">
                Open frame
              </a>
            )}
          </div>

          {transcript && (
            <div className="mt-4">
              <h4 className="font-semibold text-sm mb-1">Transcript</h4>
              <p className="text-xs text-base-content/70 max-h-24 overflow-y-auto">{transcript}</p>
            </div>
          )}

          {neighborStrip.length > 1 && (
            <div className="mt-4">
              <h4 className="font-semibold text-sm mb-2">Neighbouring frames</h4>
              <div className="flex gap-2 overflow-x-auto pb-2 scroll-smooth">
                {neighborStrip.map((item, i) => (
                  <img
                    key={`${item.path}:${i}`}
                    ref={item.current ? currentNeighborRef : undefined}
                    src={
                      item.current
                        ? item.path
                        : `${mediaConfig?.image_base_url}/${item.path}`
                    }
                    alt={item.current ? 'current frame' : item.path}
                    loading="lazy"
                    title={item.current ? 'Current frame' : undefined}
                    onLoad={item.current ? () => centreCurrentNeighbor(false) : undefined}
                    className={`h-20 w-36 object-cover rounded shrink-0 ${
                      item.current
                        ? 'border-2 border-primary ring-2 ring-primary/40'
                        : 'border border-base-300 opacity-70'
                    }`}
                  />
                ))}
              </div>
            </div>
          )}

          <div className="mt-4 border-t border-base-300 pt-4">
            <div className="flex items-center justify-between mb-2">
              <h4 className="font-semibold text-sm">
                Marked frames <span className="text-base-content/60">({markedHere.length})</span>
              </h4>
              <button
                type="button"
                className="btn btn-sm btn-outline"
                onClick={() =>
                  markFrame(videoName, fps, Math.round((videoRef.current?.currentTime ?? startSeconds ?? 0) * fps))
                }
              >
                Mark current frame
              </button>
            </div>
            {markedHere.length > 0 && (
              <ul className="flex flex-wrap gap-2">
                {markedHere.map((frameId) => (
                  <li key={frameId} className="badge badge-lg gap-2">
                    {frameId}
                    <span className="text-xs opacity-60">{formatTimecode(frameId / fps)}</span>
                    <button type="button" onClick={() => removeFrame(frameId)} aria-label={`Remove frame ${frameId}`}>
                      ✕
                    </button>
                  </li>
                ))}
              </ul>
            )}
            <p className="text-xs text-base-content/50 mt-2">
              Kept for TRAKE submission, which is not wired up yet (doc comment [b]
              defers it to the finals). The TRAKE CSV export has been removed.
            </p>
          </div>

          <div className="modal-action">
            <form method="dialog">
              <button className="btn">Close</button>
            </form>
          </div>
        </div>
      )}
      <form method="dialog" className="modal-backdrop">
        <button>close</button>
      </form>
    </dialog>
  )
}
