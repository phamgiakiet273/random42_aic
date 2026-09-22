import { useEffect } from 'react'
import { useSubmissionStore } from '../stores/submissionStore'

// Global DRES status toast: connection state + the last submit verdict
// (CORRECT green / WRONG red / error amber). Mounted once at app root.
const COLOR = {
  correct: 'alert-success',
  wrong: 'alert-error',
  error: 'alert-warning',
  info: 'alert-info',
}

export default function SubmissionStatus() {
  const last = useSubmissionStore((s) => s.last)
  const ready = useSubmissionStore((s) => s.ready)
  const message = useSubmissionStore((s) => s.message)
  const bootstrap = useSubmissionStore((s) => s.bootstrap)
  const clearLast = useSubmissionStore((s) => s.clearLast)

  // Try to establish a DRES session + active evaluation once at startup.
  useEffect(() => {
    bootstrap()
  }, [bootstrap])

  // Auto-dismiss non-error verdicts.
  useEffect(() => {
    if (last && last.kind !== 'error') {
      const t = setTimeout(clearLast, 6000)
      return () => clearTimeout(t)
    }
  }, [last, clearLast])

  return (
    <div className="toast toast-end z-50 max-w-sm">
      {!ready && (
        <div className="alert alert-warning py-1 px-3 text-xs gap-2">
          <span className="truncate">DRES: {message || 'not connected'}</span>
          <button className="btn btn-xs" onClick={() => bootstrap()}>
            retry
          </button>
        </div>
      )}
      {last && (
        <div className={`alert ${COLOR[last.kind] || 'alert-info'} py-1 px-3 text-xs gap-2`}>
          <span className="truncate">{last.text}</span>
          <button className="btn btn-xs btn-ghost" onClick={clearLast}>
            ✕
          </button>
        </div>
      )}
    </div>
  )
}
