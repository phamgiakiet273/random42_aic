// DRES submission — mounted on the hub, reached via the /submission proxy.
// Spec: docs/SUBMISSION_SPEC.md. mediaItemName is resolved to the authoritative
// (no-extension) name server-side; the UI just sends the internal video_name.
import { API_BASE_URL, ApiError } from './client'

/** True when `fps` is usable. fps varies across the dataset (950 videos at 25,
 *  359 at 30, 30 at 29.97, plus a drifting tail), so a default is never safe. */
export function isFpsKnown(fps) {
  const r = parseFloat(fps)
  return Number.isFinite(r) && r > 0
}

async function postJson(path, body) {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  const json = await res.json().catch(() => ({}))
  if (!res.ok) {
    throw new ApiError(json.detail || json.message || res.statusText, res.status)
  }
  return json.data ?? json // DRES result: { submission: "CORRECT"|"WRONG", description, ... }
}

// Under the 10 s status poll. Without a limit a stalled link (tunnel, proxy) left
// one request hanging per poll; the browser allows 6 connections per host over
// HTTP/1.1 (dev server, teammates' nginx), so after a minute nothing else loaded.
const STATUS_TIMEOUT_MS = 8000

/** The central service's DRES session + ACTIVE evaluations. Never throws —
 *  returns ok/message; `unreachable` = the server did not answer at all. */
export async function getSessionAndEval() {
  const ctrl = new AbortController()
  const timer = setTimeout(() => ctrl.abort(), STATUS_TIMEOUT_MS)
  try {
    const res = await fetch(`${API_BASE_URL}/submission/get_session_and_eval`, { signal: ctrl.signal })
    const json = await res.json().catch(() => ({}))
    return { ok: json.status === 200, message: json.message || '', ...(json.data || {}) }
  } catch (e) {
    const message = e.name === 'AbortError' ? 'the server did not answer in 8 s (tunnel down?)' : String(e)
    return { ok: false, unreachable: true, message, session_id: null, eval_id: null }
  } finally {
    clearTimeout(timer)
  }
}

export function submitKis({ sessionId, evalId, video, start, end }) {
  return postJson('/submission/submit_kis', {
    session_id: sessionId,
    eval_id: evalId,
    mediaItemName: video,
    start,
    end,
  })
}

export function submitQa({ sessionId, evalId, answer, video, time }) {
  return postJson('/submission/submit_qa', {
    session_id: sessionId,
    eval_id: evalId,
    answer,
    video_id: video,
    time: String(time),
  })
}

export function submitTrake({ sessionId, evalId, video, frameIds }) {
  return postJson('/submission/submit_trake', {
    session_id: sessionId,
    eval_id: evalId,
    video_id: video,
    frame_ids: frameIds, // "frame1,frame2,..."
  })
}
