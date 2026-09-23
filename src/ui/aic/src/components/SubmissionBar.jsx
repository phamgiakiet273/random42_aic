import { useSubmissionStore } from '../stores/submissionStore'
import { useSettingsStore } from '../stores/settingsStore'

const MODES = [
  ['kis', 'KIS'],
  ['qa', 'Q&A'],
  ['trake', 'TRAKE'],
]

// Persistent submission control in the header: pick the task mode (KIS/Q&A/TRAKE),
// type the Q&A answer or submit the marked TRAKE sequence, see the DRES connection,
// and toggle confirm-before-submit. The per-frame Submit buttons follow this mode.
export default function SubmissionBar() {
  const mode = useSubmissionStore((s) => s.mode)
  const setMode = useSubmissionStore((s) => s.setMode)
  const qaAnswer = useSubmissionStore((s) => s.qaAnswer)
  const setQaAnswer = useSubmissionStore((s) => s.setQaAnswer)
  const trake = useSubmissionStore((s) => s.trake)
  const clearTrake = useSubmissionStore((s) => s.clearTrake)
  const submitTrakeNow = useSubmissionStore((s) => s.submitTrakeNow)
  const ready = useSubmissionStore((s) => s.ready)
  const evalId = useSubmissionStore((s) => s.evalId)
  const evalName = useSubmissionStore((s) => s.evalName)
  const bootstrap = useSubmissionStore((s) => s.bootstrap)
  const busy = useSubmissionStore((s) => s.busy)
  const confirmSubmit = useSettingsStore((s) => s.confirmSubmit)
  const update = useSettingsStore((s) => s.update)

  return (
    <div className="flex items-center gap-2 mr-2">
      <span
        className={`badge badge-sm ${ready ? 'badge-success text-white' : 'badge-ghost'}`}
        title={ready ? `active evaluation ${evalName || ''} (${evalId})` : 'no DRES session / active evaluation'}
      >
        DRES{ready ? '' : ' ✕'}
      </span>
      {!ready && (
        <button className="btn btn-xs" onClick={() => bootstrap()}>
          connect
        </button>
      )}

      <div className="join">
        {MODES.map(([m, lbl]) => (
          <button
            key={m}
            className={`btn btn-xs join-item ${mode === m ? 'btn-primary' : 'btn-ghost'}`}
            onClick={() => setMode(m)}
          >
            {lbl}
          </button>
        ))}
      </div>

      {mode === 'qa' && (
        <input
          className="input input-xs input-bordered w-44"
          placeholder="Q&A answer…"
          value={qaAnswer}
          onChange={(e) => setQaAnswer(e.target.value)}
        />
      )}

      {mode === 'trake' && (
        <div className="flex items-center gap-1">
          <span className="text-xs opacity-70 max-w-[16rem] truncate">
            {trake.length ? `${trake[0].video}: ${trake.map((t) => t.frame).join(',')}` : 'mark frames on results…'}
          </span>
          <button
            className="btn btn-xs btn-success text-white"
            disabled={!trake.length || busy}
            onClick={() => submitTrakeNow()}
          >
            Submit TRAKE
          </button>
          <button className="btn btn-xs btn-ghost" disabled={!trake.length} onClick={() => clearTrake()}>
            clear
          </button>
        </div>
      )}

      <label className="label cursor-pointer gap-1 py-0" title="Confirm each submit before sending to DRES">
        <input
          type="checkbox"
          className="toggle toggle-xs"
          checked={confirmSubmit}
          onChange={(e) => update({ confirmSubmit: e.target.checked })}
        />
        <span className="label-text text-xs">confirm</span>
      </label>
    </div>
  )
}
