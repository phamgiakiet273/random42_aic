import { create } from 'zustand'
import {
  getSessionAndEval,
  submitKis,
  submitQa,
  submitTrake,
  frameTimeMs,
} from '../api/submission'

// Per-evaluation dup-guard key: submitting the identical answer twice is wasted
// (DRES rejects it) and every wrong submit before the first correct costs points.
const answerKey = (evalId, sig) => `${evalId}||${sig}`

function verdictOf(res) {
  const v = String(res?.submission || res?.status || '').toUpperCase()
  if (v === 'CORRECT' || v === 'TRUE') return 'correct'
  if (v === 'WRONG' || v === 'INCORRECT' || v === 'FALSE') return 'wrong'
  if (v === 'INDETERMINATE' || v === 'UNDECIDABLE') return 'info'
  return 'info'
}

export const useSubmissionStore = create((set, get) => ({
  sessionId: null,
  evalId: null,
  ready: false, // logged in AND an ACTIVE evaluation exists
  message: '',
  busy: false,
  last: null, // { kind: 'correct'|'wrong'|'error'|'info', text }
  submitted: new Set(), // dup-guard keys

  clearLast: () => set({ last: null }),

  async bootstrap() {
    const r = await getSessionAndEval()
    set({
      sessionId: r.session_id || null,
      evalId: r.eval_id || null,
      ready: !!(r.ok && r.eval_id),
      message: r.message || '',
    })
    return r
  },

  async _ensureReady() {
    if (get().ready && get().sessionId && get().evalId) return true
    const r = await get().bootstrap()
    if (!(r.ok && r.eval_id)) {
      set({ last: { kind: 'error', text: r.message || 'Not logged in / no active evaluation' } })
      return false
    }
    return true
  },

  async _submit(sig, doCall, label) {
    if (!(await get()._ensureReady())) return
    const key = answerKey(get().evalId, sig)
    if (get().submitted.has(key)) {
      set({ last: { kind: 'info', text: `Already submitted — ${label}` } })
      return
    }
    set({ busy: true, last: { kind: 'info', text: `Submitting ${label}…` } })
    try {
      const res = await doCall()
      const kind = verdictOf(res)
      const desc = res?.description ? ` — ${res.description}` : ''
      set((s) => ({
        submitted: new Set(s.submitted).add(key),
        last: { kind, text: `${kind.toUpperCase()}: ${label}${desc}` },
      }))
    } catch (e) {
      set({ last: { kind: 'error', text: `Submit failed (${label}): ${e.message}` } })
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
        text: `Cannot submit ${video}: its fps is unknown, so the frame's timestamp cannot be computed.`,
      },
    })
  },

  // KIS one-click on a result frame (video_name + keyframe_id + fps).
  submitFrameKis(record) {
    const video = record.video_name
    const ms = frameTimeMs(record.keyframe_id, record.fps)
    if (ms == null) return get()._refuseUnknownFps(video)
    const label = `KIS ${video} @ ${ms}ms`
    return get()._submit(`KIS|${video}|${ms}`, () =>
      submitKis({ sessionId: get().sessionId, evalId: get().evalId, video, start: ms, end: ms }),
      label,
    )
  },

  // Q&A: an answer for the found frame.
  submitQaAnswer(record, answer) {
    const video = record.video_name
    const ms = frameTimeMs(record.keyframe_id, record.fps)
    if (ms == null) return get()._refuseUnknownFps(video)
    const label = `QA "${answer}" ${video} @ ${ms}ms`
    return get()._submit(`QA|${answer}|${video}|${ms}`, () =>
      submitQa({ sessionId: get().sessionId, evalId: get().evalId, answer, video, time: ms }),
      label,
    )
  },

  // TRAKE: an ordered list of frame numbers from ONE video.
  submitTrakeFrames(video, frameIds) {
    const ids = frameIds.map((f) => String(parseInt(f, 10))).join(',')
    const label = `TRAKE ${video} [${ids}]`
    return get()._submit(`TR|${video}|${ids}`, () =>
      submitTrake({ sessionId: get().sessionId, evalId: get().evalId, video, frameIds: ids }),
      label,
    )
  },

  // ---- task mode (drives what the per-frame Submit button does) ----
  mode: 'kis', // 'kis' | 'qa' | 'trake'
  qaAnswer: '',
  trake: [], // [{ video, frame }] — TRAKE answers must all come from ONE video
  setMode: (mode) => set({ mode }),
  setQaAnswer: (qaAnswer) => set({ qaAnswer }),
  clearTrake: () => set({ trake: [] }),
  removeTrakeFrame: (frame) =>
    set((s) => ({ trake: s.trake.filter((t) => t.frame !== frame) })),

  /** Load a whole temporal-search chain as the TRAKE sequence, in the chain's
   *  own event order (NOT re-sorted by frame number, unlike addTrakeFrame) —
   *  that order is what the backend already matched the query's events to.
   *  Replaces any work-in-progress sequence, same as switching video does. */
  loadTrakeChain(video, frameIds) {
    const trake = frameIds.map((frame) => ({ video, frame }))
    set({
      mode: 'trake',
      trake,
      last: { kind: 'info', text: `TRAKE loaded: ${video} [${frameIds.join(',')}]` },
    })
  },

  addTrakeFrame(record) {
    const video = record.video_name
    const frame = parseInt(record.keyframe_id, 10)
    set((s) => {
      const same = s.trake.length === 0 || s.trake[0].video === video
      const base = same ? s.trake : [] // switching video restarts the sequence
      if (base.some((t) => t.frame === frame)) return {}
      const trake = [...base, { video, frame }].sort((a, b) => a.frame - b.frame)
      return { trake, last: { kind: 'info', text: `TRAKE +${video}#${frame} (${trake.length})` } }
    })
  },

  submitTrakeNow() {
    const t = get().trake
    if (!t.length) {
      set({ last: { kind: 'error', text: 'No TRAKE frames marked' } })
      return
    }
    return get().submitTrakeFrames(
      t[0].video,
      t.map((x) => x.frame),
    )
  },

  // The mode-aware action the per-frame Submit button calls.
  actOnFrame(record) {
    const m = get().mode
    if (m === 'qa') return get().submitQaAnswer(record, get().qaAnswer)
    if (m === 'trake') return get().addTrakeFrame(record)
    return get().submitFrameKis(record)
  },
}))
