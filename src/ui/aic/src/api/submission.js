// DRES submission — mounted on the hub, reached via the /submission proxy.
// Spec: docs/SUBMISSION_SPEC.md. mediaItemName is resolved to the authoritative
// (no-extension) name server-side; the UI just sends the internal video_name.
import { API_BASE_URL, ApiError } from './client'

/** Frame's time in the original video, ms: round(frame_idx / fps * 1000). */
export function frameTimeMs(frameId, fps) {
  const f = parseInt(frameId, 10) || 0
  const r = parseFloat(fps) || 1
  return Math.round((f / r) * 1000)
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

/** Lazy login + the ACTIVE evaluation id. Never throws — returns ok/message. */
export async function getSessionAndEval() {
  try {
    const res = await fetch(`${API_BASE_URL}/submission/get_session_and_eval`)
    const json = await res.json().catch(() => ({}))
    return { ok: json.status === 200, message: json.message || '', ...(json.data || {}) }
  } catch (e) {
    return { ok: false, message: String(e), session_id: null, eval_id: null }
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
