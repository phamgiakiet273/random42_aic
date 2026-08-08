import { useEffect, useRef } from 'react'

export default function FrameDetailModal({ video, onClose }) {
  const dialogRef = useRef(null)

  useEffect(() => {
    const dialog = dialogRef.current
    if (!dialog) return
    if (video) {
      dialog.showModal()
    } else {
      dialog.close()
    }
  }, [video])

  return (
    <dialog ref={dialogRef} className="modal" onClose={onClose}>
      {video && (
        <div className="modal-box max-w-2xl">
          <h3 className="font-semibold text-lg">{video.title}</h3>
          <p className="text-sm text-base-content/60 mb-4">
            {video.video_id} · {video.timestamp}
          </p>
          <img
            src={video.thumbnail_url}
            alt={video.title}
            className="w-full rounded-lg aspect-video object-cover"
          />
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
