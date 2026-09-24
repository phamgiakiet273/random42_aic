// Same-origin by default: /hub is proxied by the dev server, so an absolute
// `localhost:9021` (which resolves to the *viewer's* machine when remote) never
// reaches the page. Set VITE_API_BASE_URL to use a different origin.
export const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || '').replace(
  /\/+$/,
  '',
)

export class ApiError extends Error {
  constructor(message, status) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

function toFormData(fields) {
  const body = new FormData()
  for (const [key, value] of Object.entries(fields)) {
    if (value === undefined || value === null || value === '') continue
    // The hub takes list-valued fields (frame_class_filter, skip_frames) as
    // JSON strings inside form-data, so arrays/objects are stringified here.
    body.append(key, typeof value === 'object' ? JSON.stringify(value) : String(value))
  }
  return body
}

// Remote users reach the server through ngrok agents whose sessions to ngrok's
// edge drop now and then. A request caught by a drop either fails AT NGROK
// (502/503/504, or a response carrying its `ngrok-error-code` header, e.g. the 404
// "endpoint offline"), fails at the network, or HANGS on the stalled session until
// ngrok gives up (seen as "down for a minute"). The calls below only read (search,
// video list, CSV...), so each attempt gets a time limit and a failed or stuck one
// is resent (a new request, which ngrok can route to a healthy agent). Submissions
// never come through here (api/submission.js): resending an answer could duplicate it.
const ATTEMPT_TIMEOUT_MS = 25000 // the heaviest search (6-event temporal, top-K 1000) takes ~3 s
const RETRY_DELAYS_MS = [1000, 2500] // up to 2 retries

function transient(res) {
  return res.status === 502 || res.status === 503 || res.status === 504 || res.headers.has('ngrok-error-code')
}

async function fetchWithRetry(url, makeInit = () => ({})) {
  for (let attempt = 0; ; attempt++) {
    const last = attempt >= RETRY_DELAYS_MS.length
    const timeout = new AbortController()
    const timer = setTimeout(() => timeout.abort(), ATTEMPT_TIMEOUT_MS)
    try {
      const res = await fetch(url, { ...makeInit(), signal: timeout.signal })
      if (!transient(res) || last) return res
    } catch (err) {
      if (last) throw err.name === 'AbortError' ? new ApiError('The server did not answer (tunnel down?) -- try again', 504) : err
    } finally {
      clearTimeout(timer)
    }
    await new Promise((resolve) => setTimeout(resolve, RETRY_DELAYS_MS[attempt]))
  }
}

// Every hub endpoint returns {status, message, data}; callers want `data`.
export async function postForm(path, fields) {
  const res = await fetchWithRetry(`${API_BASE_URL}${path}`, () => ({
    method: 'POST',
    body: toFormData(fields),
  }))
  return unwrap(res)
}

// `base` targets a service other than the hub (e.g. the result manager).
export async function get(path, base = API_BASE_URL) {
  const res = await fetchWithRetry(`${base}${path}`)
  return unwrap(res)
}

// Returns the raw Response — for endpoints that are not JSON (CSV export).
export async function postFormRaw(path, fields) {
  const res = await fetchWithRetry(`${API_BASE_URL}${path}`, () => ({
    method: 'POST',
    body: toFormData(fields),
  }))
  if (!res.ok) throw new ApiError(await readError(res), res.status)
  return res
}

async function unwrap(res) {
  if (!res.ok) throw new ApiError(await readError(res), res.status)
  const json = await res.json()
  if (json && typeof json === 'object' && 'data' in json) return json.data
  return json
}

async function readError(res) {
  try {
    const body = await res.json()
    return body?.detail || body?.message || `${res.status} ${res.statusText}`
  } catch {
    return `${res.status} ${res.statusText}`
  }
}
