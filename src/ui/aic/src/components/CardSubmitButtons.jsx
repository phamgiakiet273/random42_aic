import { useSubmissionStore } from '../stores/submissionStore'
import { isFpsKnown } from '../api/submission'

// The legacy card buttons, one explicit action each (no global mode):
//   K   submit this frame as KIS, one click (Settings -> confirm gates it)
//   Q   open the Q&A dialog for this frame (type the answer, Enter submits)
//   TR  open the frame viewer on the TRAKE timeline for this video (nothing marked)
// All three need the video's fps: KIS/Q&A send a time (frame / fps) and TRAKE
// events are placed on the player's timeline.
export default function CardSubmitButtons({ record, className = '' }) {
  const submitFrameKis = useSubmissionStore((s) => s.submitFrameKis)
  const openQa = useSubmissionStore((s) => s.openQa)
  const openViewer = useSubmissionStore((s) => s.openViewer)
  const busy = useSubmissionStore((s) => s.busy)
  const fpsKnown = isFpsKnown(record.fps)
  const why = "Unavailable: this video's fps is unknown, so the frame time cannot be computed"

  // [letter, aria-label, tooltip, action, disabled]
  const buttons = [
    ['K', 'Submit this frame to DRES as KIS', 'K: submit this frame to DRES as KIS (one click)', () => submitFrameKis(record), busy],
    ['Q', 'Q&A: answer for this frame', 'Q: Q&A answer for this frame (Enter submits, Esc cancels)', () => openQa(record), false],
    ['TR', 'TRAKE: mark events on this video', 'TR: TRAKE, mark events on this video (M marks, drag to move)', () => openViewer(record, { tab: 'trake' }), false],
  ]
  // Same look as the card's other buttons (browse shot / similar frames).
  return (
    <div className={`flex gap-1 opacity-60 hover:opacity-100 focus-within:opacity-100 transition-opacity ${className}`}>
      {buttons.map(([letter, label, tip, act, disabled]) => (
        <button
          key={letter}
          type="button"
          className="btn btn-circle btn-xs font-bold"
          title={fpsKnown ? tip : why}
          aria-label={label}
          disabled={disabled || !fpsKnown}
          onClick={(e) => {
            e.stopPropagation()
            act()
          }}
        >
          {letter}
        </button>
      ))}
    </div>
  )
}
