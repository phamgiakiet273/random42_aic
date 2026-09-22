import { Send, Plus } from 'lucide-react'
import { useSubmissionStore } from '../stores/submissionStore'
import { useSettingsStore } from '../stores/settingsStore'
import { frameTimeMs } from '../api/submission'

// One-click submit for a single result frame. The active task mode (KIS/QA/TRAKE,
// from the submission bar) decides what it does:
//   KIS  -> submit this frame's video + time as a KIS answer
//   QA   -> submit the bar's answer text for this frame
//   TRAKE-> add this frame to the marked sequence (submit the whole list from the bar)
// Direct by default; Settings → "Confirm before submit" gates real submits (not TRAKE-add).
export default function SubmitButton({ record, label = false, className = '' }) {
  const mode = useSubmissionStore((s) => s.mode)
  const qaAnswer = useSubmissionStore((s) => s.qaAnswer)
  const actOnFrame = useSubmissionStore((s) => s.actOnFrame)
  const busy = useSubmissionStore((s) => s.busy)
  const confirmSubmit = useSettingsStore((s) => s.confirmSubmit)

  function onClick(e) {
    e.stopPropagation()
    const ms = frameTimeMs(record.keyframe_id, record.fps)
    if (mode === 'trake') {
      actOnFrame(record) // just collects; the bar submits the sequence
      return
    }
    if (mode === 'qa' && !qaAnswer.trim()) {
      window.alert('Type the Q&A answer in the submission bar first.')
      return
    }
    const what =
      mode === 'qa'
        ? `Q&A "${qaAnswer}"\n${record.video_name} @ ${ms} ms`
        : `KIS ${record.video_name} @ ${ms} ms`
    if (confirmSubmit && !window.confirm(`Submit to DRES?\n${what}`)) return
    actOnFrame(record)
  }

  const isTrake = mode === 'trake'
  return (
    <button
      type="button"
      className={`btn btn-xs ${isTrake ? 'btn-warning' : 'btn-success'} text-white gap-1 ${className}`}
      title={
        isTrake ? 'Add this frame to the TRAKE sequence' : `Submit this frame to DRES (${mode.toUpperCase()})`
      }
      onClick={onClick}
      disabled={busy}
    >
      {isTrake ? <Plus size={12} /> : <Send size={12} />}
      {label && (isTrake ? 'TRAKE+' : 'Submit')}
    </button>
  )
}
