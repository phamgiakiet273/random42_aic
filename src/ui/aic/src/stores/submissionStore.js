import { create } from 'zustand'
import { getSessionAndEval, submitKis, submitQa, submitTrake } from '../api/submission'
import { frameMs } from '../api/timing'
import { videoStem } from '../api/media'
import { useSettingsStore } from './settingsStore'

// Duplicate answers are refused by the central submission service (team-wide,
// per evaluation, time-windowed), which answers 409 -- no client-side guard, so
// teammates and the server UI share one source of truth.

function verdictOf(res) {
  const v = String(res?.submission || res?.status || '').toUpperCase()
  if (v === 'CORRECT' || v === 'TRUE') return 'correct'
  if (v === 'WRONG' || v === 'INCORRECT' || v === 'FALSE') return 'wrong'
  if (v === 'INDETERMINATE' || v === 'UNDECIDABLE') return 'info'
  return 'info'
}

const CHOSEN_EVAL_KEY = 'aic.dres.chosenEvalId'
function loadChosenEval() {
  try {
    return window.localStorage.getItem(CHOSEN_EVAL_KEY) || null
  } catch {
    return null
  }
}
function saveChosenEval(id) {
  try {
    if (id) window.localStorage.setItem(CHOSEN_EVAL_KEY, id)
    else window.localStorage.removeItem(CHOSEN_EVAL_KEY)
  } catch {
    /* storage unavailable: the choice lasts until reload */
  }
}

// Submissions (KIS / Q&A / TRAKE) are explicit per-frame actions, like the legacy
// K / Q / TR card buttons; there is no global mode. Video names are sent
// extension-less (videoStem); the server maps them to the official DRES names.
export const useSubmissionStore = create((set, get) => ({
  sessionId: null,
  evalId: null,
  evalName: null,
  ready: false, // logged in AND an evaluation to submit to (the chosen / only ACTIVE one)
  // DRES can run several evaluations at once: all ACTIVE ones, and the one this
  // browser chose in the header (remembered; cleared when it is no longer ACTIVE).
  evaluations: [], // [{ id, name }]
  chosenEvalId: loadChosenEval(),
  message: '',
  busy: false,
  last: null, // { kind: 'correct'|'wrong'|'error'|'info', text }

  clearLast: () => set({ last: null }),

  async bootstrap() {
    const r = await getSessionAndEval()
    const evaluations = Array.isArray(r.evaluations) ? r.evaluations : []
    set({ sessionId: r.session_id || null, evaluations })
    get()._applyChoice(r.ok, r.message || '')
    return r
  },

  /** Pick the evaluation to submit to: the chosen one while it is ACTIVE, else
   *  the only ACTIVE one. With several ACTIVE and none chosen there is none:
   *  guessing could put an answer in the wrong evaluation. */
  _applyChoice(ok = get().sessionId != null, message = get().message) {
    const { evaluations } = get()
    let chosen = get().chosenEvalId
    if (chosen && !evaluations.some((e) => e.id === chosen)) {
      chosen = null // it ended
      saveChosenEval(null)
    }
    const current = evaluations.find((e) => e.id === chosen) || (evaluations.length === 1 ? evaluations[0] : null)
    set({
      chosenEvalId: chosen,
      evalId: current?.id || null,
      evalName: current?.name || null,
      ready: !!(ok && current),
      message: evaluations.length > 1 && !current ? `${evaluations.length} evaluations are ACTIVE: choose one in the header` : message,
    })
  },

  chooseEval(id) {
    saveChosenEval(id || null)
    set({ chosenEvalId: id || null })
    get()._applyChoice()
  },

  async _ensureReady() {
    if (get().ready && get().sessionId && get().evalId) return true
    const r = await get().bootstrap()
    if (!get().ready) {
      set({ last: { kind: 'error', text: get().message || r.message || 'Not logged in / no active evaluation' } })
      return false
    }
    return true
  },

  async _submit(doCall, label) {
    if (!(await get()._ensureReady())) return
    set({ busy: true, last: { kind: 'info', text: `Submitting ${label}…` } })
    try {
      const res = await doCall()
      const kind = verdictOf(res)
      const desc = res?.description ? ` — ${res.description}` : ''
      set({ last: { kind, text: `${kind.toUpperCase()}: ${label}${desc}` } })
    } catch (e) {
      // 409 = the team already sent this exact answer (or no ACTIVE evaluation):
      // nothing was sent, so it is information, not a failure to retry.
      const kind = e.status === 409 ? 'info' : 'error'
      set({ last: { kind, text: `${kind === 'info' ? 'Not sent' : 'Submit failed'} (${label}): ${e.message}` } })
    } finally {
      set({ busy: false })
    }
  },

  /** KIS/Q&A answers are submitted as a time in ms, which only exists if the
   *  video's fps is known. Refuse rather than send a guessed time: a wrong
   *  submission is scored as wrong, so it costs more than not submitting. */
  _refuseUnknownFps(video) {
    set({
      last: {
        kind: 'error',
        text: `Cannot submit ${video}: the frame's time cannot be computed (fps unknown or no valid frame number).`,
      },
    })
  },

  /** The frame's real time (ms) for a DRES answer: api/timing.js (a per-frame
   *  table on the irregular traffic cams, else frame / fps). null = cannot be
   *  computed; undefined = the timing data did not load (already reported). */
  async _frameMs(record) {
    try {
      return await frameMs(record.video_name, record.keyframe_id, record.fps)
    } catch (e) {
      set({
        last: {
          kind: 'error',
          text: `Not sent: could not load the frame timing for ${videoStem(record.video_name)} (${e.message}). Retry.`,
        },
      })
      return undefined
    }
  },

  /** Settings -> "confirm before submit" gates EVERY submit path (card buttons,
   *  the Q&A dialog, the frame viewer), so it lives here rather than per button. */
  _confirmed(what) {
    if (!useSettingsStore.getState().confirmSubmit) return true
    const to = get().evaluations.length > 1 ? `\nto evaluation: ${get().evalName}` : ''
    return window.confirm(`Submit to DRES?\n${what}${to}`)
  },

  // KIS: this frame's video + time.
  async submitFrameKis(record) {
    const video = videoStem(record.video_name)
    const ms = await get()._frameMs(record)
    if (ms === undefined) return
    if (ms == null) return get()._refuseUnknownFps(video)
    const label = `KIS ${video} @ ${ms}ms`
    if (!get()._confirmed(label)) return
    return get()._submit(() =>
      submitKis({ sessionId: get().sessionId, evalId: get().evalId, video, start: ms, end: ms }),
      label,
    )
  },

  // Q&A: an answer for this frame.
  async submitQaAnswer(record, answer) {
    const video = videoStem(record.video_name)
    // NFC + single spaces: DRES compares the text exactly (case aside)
    const text = String(answer ?? '').normalize('NFC').replace(/\s+/g, ' ').trim()
    if (!text) {
      set({ last: { kind: 'error', text: 'Type the Q&A answer first' } })
      return
    }
    const ms = await get()._frameMs(record)
    if (ms === undefined) return
    if (ms == null) return get()._refuseUnknownFps(video)
    const label = `QA "${text}" ${video} @ ${ms}ms`
    if (!get()._confirmed(label)) return
    return get()._submit(() =>
      submitQa({ sessionId: get().sessionId, evalId: get().evalId, answer: text, video, time: ms }),
      label,
    )
  },

  // TRAKE: the event frames of ONE video, in timeline order.
  submitTrakeFrames(videoName, frameIds) {
    const video = videoStem(videoName)
    const frames = frameIds.map((f) => parseInt(f, 10)).filter(Number.isFinite)
    if (!frames.length) {
      set({ last: { kind: 'error', text: 'No TRAKE events marked' } })
      return
    }
    const ids = frames.join(',')
    const label = `TRAKE ${video} [${ids}]`
    if (!get()._confirmed(label)) return
    return get()._submit(() =>
      submitTrake({ sessionId: get().sessionId, evalId: get().evalId, video, frameIds: ids }),
      label,
    )
  },

  // ---- the frame viewer: ONE per page, opened by a card click, a card's TR, or a
  // temporal chain's "Use as TRAKE". `tab` picks the submission panel shown first;
  // `marks` pre-fills TRAKE events (only a loaded chain does). `nonce` makes every
  // open a fresh viewer, even for the same frame.
  viewer: null, // { record, tab: 'kis' | 'qa' | 'trake', marks: number[], nonce }
  openViewer: (record, { tab = 'kis', marks = [] } = {}) =>
    set({ viewer: { record, tab, marks, nonce: Date.now() } }),
  closeViewer: () => set({ viewer: null }),

  // ---- the per-card Q&A dialog (a card's Q)
  qaRecord: null,
  openQa: (record) => set({ qaRecord: record }),
  closeQa: () => set({ qaRecord: null }),
}))
