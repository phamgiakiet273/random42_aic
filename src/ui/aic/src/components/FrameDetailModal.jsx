import { useEffect, useRef, useState } from 'react'
import { useTrakeStore } from '../stores/trakeStore'
import { submitTrake } from '../api/dummy'

const DEFAULT_FPS = 25

function frameToSeconds(keyframeId, fps) {
  return keyframeId / (fps || DEFAULT_FPS)
}

function formatStartTime(totalSeconds) {
  const h = String(Math.floor(totalSeconds / 3600)).padStart(2, '0')
  const m = String(Math.floor((totalSeconds % 3600) / 60)).padStart(2, '0')
  const s = String(Math.floor(totalSeconds % 60)).padStart(2, '0')
  return `${h}:${m}:${s}`
}

export default function FrameDetailModal({ video, onClose }) {
  const dialogRef = useRef(null)
  const videoRef = useRef(null)
  const [submitStatus, setSubmitStatus] = useState(null)

  const trakeVideoId = useTrakeStore((s) => s.videoId)
  const trakeFrames = useTrakeStore((s) => s.frames)
  const markFrame = useTrakeStore((s) => s.markFrame)
  const removeFrame = useTrakeStore((s) => s.removeFrame)
  const clearTrake = useTrakeStore((s) => s.clear)

  const startTime =
    video?.keyframe_id != null ? frameToSeconds(video.keyframe_id, video.fps) : null

  const trakeEnabled = video?.fps != null
  const framesForThisVideo = trakeEnabled && trakeVideoId === video.video_id ? trakeFrames : []

  useEffect(() => {
    const dialog = dialogRef.current
    if (!dialog) return
    if (video) {
      dialog.showModal()
    } else {
      dialog.close()
    }
    setSubmitStatus(null)
  }, [video])

  useEffect(() => {
    const el = videoRef.current
    if (!el || startTime == null) return
    const seekToStart = () => {
      el.currentTime = startTime
    }
    el.addEventListener('loadedmetadata', seekToStart)
    return () => el.removeEventListener('loadedmetadata', seekToStart)
  }, [video?.video_path, startTime])

  const handleMark = () => {
    const fps = video.fps || DEFAULT_FPS
    const currentTime = videoRef.current?.currentTime ?? startTime ?? 0
    const frameId = Math.round(currentTime * fps)
    markFrame(video.video_id, fps, frameId)
  }

  const handleSubmit = async () => {
    setSubmitStatus('submitting')
    await submitTrake(video.video_id, framesForThisVideo)
    setSubmitStatus('submitted')
    clearTrake()
  }

  return (
    <dialog ref={dialogRef} className="modal" onClose={onClose}>
      {video && (
        <div className="modal-box max-w-2xl">
          <h3 className="font-semibold text-lg">{video.title}</h3>
          <p className="text-sm text-base-content/60 mb-4">
            {video.video_id} · {video.timestamp}
            {startTime != null && <> · Start: {formatStartTime(startTime)}</>}
          </p>
          {video.video_path ? (
            <video
              key={video.video_path}
              ref={videoRef}
              src={startTime != null ? `${video.video_path}#t=${startTime}` : video.video_path}
              poster={video.thumbnail_url}
              controls
              autoPlay
              className="w-full rounded-lg aspect-video bg-black"
            />
          ) : (
            <img
              src={video.thumbnail_url}
              alt={video.title}
              className="w-full rounded-lg aspect-video object-cover"
            />
          )}
          {trakeEnabled && (
            <div className="mt-4 border-t border-base-300 pt-4">
              <div className="flex items-center justify-between mb-2">
                <h4 className="font-semibold text-sm">
                  Marked Frames{' '}
                  <span className="text-base-content/60">({framesForThisVideo.length})</span>
                </h4>
                <button type="button" className="btn btn-sm btn-outline" onClick={handleMark}>
                  Mark Current Frame
                </button>
              </div>
              {framesForThisVideo.length > 0 && (
                <ul className="flex flex-wrap gap-2 mb-3">
                  {framesForThisVideo.map((frameId) => (
                    <li key={frameId} className="badge badge-lg gap-2">
                      {frameId}
                      <span className="text-xs opacity-60">
                        {formatStartTime(frameToSeconds(frameId, video.fps))}
                      </span>
                      <button
                        type="button"
                        className="opacity-60 hover:opacity-100"
                        onClick={() => removeFrame(frameId)}
                        aria-label={`Remove frame ${frameId}`}
                      >
                        ✕
                      </button>
                    </li>
                  ))}
                </ul>
              )}
              <button
                type="button"
                className="btn btn-sm btn-primary"
                disabled={framesForThisVideo.length === 0 || submitStatus === 'submitting'}
                onClick={handleSubmit}
              >
                Submit TRAKE
              </button>
              {submitStatus === 'submitted' && (
                <span className="ml-2 text-success text-sm">Submitted</span>
              )}
            </div>
          )}
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
