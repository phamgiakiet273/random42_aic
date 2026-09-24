import { useSubmissionStore } from '../stores/submissionStore'
import { useSettingsStore } from '../stores/settingsStore'

// Header: the DRES connection and the confirm-before-submit toggle. Submitting is
// done per frame (a card's K / Q / TR, or the frame viewer), never through a mode.
export default function SubmissionBar() {
  const ready = useSubmissionStore((s) => s.ready)
  const evalId = useSubmissionStore((s) => s.evalId)
  const evalName = useSubmissionStore((s) => s.evalName)
  const evaluations = useSubmissionStore((s) => s.evaluations)
  const chooseEval = useSubmissionStore((s) => s.chooseEval)
  const bootstrap = useSubmissionStore((s) => s.bootstrap)
  const confirmSubmit = useSettingsStore((s) => s.confirmSubmit)
  const update = useSettingsStore((s) => s.update)

  return (
    <div className="flex items-center gap-2 mr-2">
      {evaluations.length > 1 ? (
        // DRES runs several evaluations at once: submit to the one chosen here
        <label className="flex items-center gap-1" title="Which ACTIVE DRES evaluation your submissions go to">
          <span className="text-xs text-base-content/60">DRES</span>
          <select
            className={`select select-bordered select-xs max-w-56 ${evalId ? '' : 'select-warning'}`}
            value={evalId || ''}
            onChange={(e) => chooseEval(e.target.value)}
            aria-label="DRES evaluation to submit to"
          >
            {!evalId && <option value="">choose evaluation…</option>}
            {evaluations.map((ev) => (
              <option key={ev.id} value={ev.id}>{ev.name || ev.id}</option>
            ))}
          </select>
        </label>
      ) : (
        <span
          className={`badge badge-sm ${ready ? 'badge-success text-white' : 'badge-ghost'}`}
          title={ready ? `active evaluation ${evalName || ''} (${evalId})` : 'no DRES session / active evaluation'}
        >
          DRES{ready ? `: ${evalName || 'active'}` : ' ✕'}
        </span>
      )}
      {!ready && (
        <button className="btn btn-xs" onClick={() => bootstrap()}>
          connect
        </button>
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
