import { useEffect, useRef, useState } from 'react'
import { useSubmissionStore } from '../stores/submissionStore'
import { useQuery } from '@tanstack/react-query'
import { videoStem, formatTimecode } from '../api/media'
import { frameMs } from '../api/timing'
import { isEnter } from '../utils/keys'

// A card's Q: the answer for THIS frame, like the legacy Q&A dialog. The box starts
// empty; Enter submits, Esc cancels. Mounted once at the app root.
export default function QaDialog() {
  const record = useSubmissionStore((s) => s.qaRecord)
  const closeQa = useSubmissionStore((s) => s.closeQa)
  const submitQaAnswer = useSubmissionStore((s) => s.submitQaAnswer)
  const busy = useSubmissionStore((s) => s.busy)
  const dialogRef = useRef(null)

  useEffect(() => {
    const dialog = dialogRef.current
    if (!dialog) return
    if (record) dialog.showModal()
    else if (dialog.open) dialog.close()
  }, [record])

  return (
    <dialog ref={dialogRef} className="modal" onClose={closeQa}>
      {record && (
        <QaForm
          key={`${record.video_name}:${record.keyframe_id}`}
          record={record}
          busy={busy}
          onSubmit={(answer) => {
            submitQaAnswer(record, answer)
            closeQa()
          }}
          onCancel={closeQa}
        />
      )}
      <form method="dialog" className="modal-backdrop">
        <button>close</button>
      </form>
    </dialog>
  )
}

// Keyed per frame: every open starts with an empty answer.
function QaForm({ record, busy, onSubmit, onCancel }) {
  const [answer, setAnswer] = useState('')
  const inputRef = useRef(null)
  useEffect(() => {
    inputRef.current?.focus()
  }, [])
  const submit = () => (answer.trim() ? onSubmit(answer) : inputRef.current?.focus())
  const video = videoStem(record.video_name)
  // the same time the submission will carry (api/timing.js)
  const { data: ms } = useQuery({
    queryKey: ['frameMs', video, record.keyframe_id, record.fps],
    queryFn: () => frameMs(record.video_name, record.keyframe_id, record.fps),
    staleTime: 60 * 1000, // the timing index is re-read every 5 min (api/timing.js)
  })

  return (
        <div className="modal-box max-w-md">
          <h3 className="font-semibold text-lg">Q&amp;A submission</h3>
          <p className="text-sm text-base-content/70 mt-1">
            <strong>{video}</strong> · frame {record.keyframe_id}
            {ms != null && <> · {formatTimecode(ms / 1000)} ({ms} ms)</>}
          </p>
          <input
            ref={inputRef}
            className="input input-bordered w-full mt-4"
            placeholder="Answer… (Enter submits, Esc cancels)"
            value={answer}
            onChange={(e) => setAnswer(e.target.value)}
            onKeyDown={(e) => {
              if (isEnter(e)) {
                e.preventDefault()
                submit()
              }
            }}
          />
          <div className="modal-action">
            <button type="button" className="btn" onClick={onCancel} title="Cancel (Esc)">Cancel</button>
            <button type="button" className="btn btn-primary" disabled={busy || !answer.trim()} onClick={submit} title="Submit (Enter)">
              Submit Q&amp;A
            </button>
          </div>
        </div>
  )
}
