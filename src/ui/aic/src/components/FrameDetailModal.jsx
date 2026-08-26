import { useEffect, useRef } from 'react'

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

  const startTime =
    video?.keyframe_id != null ? frameToSeconds(video.keyframe_id, video.fps) : null

  useEffect(() => {
    const dialog = dialogRef.current
    if (!dialog) return
    if (video) {
      dialog.showModal()
    } else {
      dialog.close()
    }
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
