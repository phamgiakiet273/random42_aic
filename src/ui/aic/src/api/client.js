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

// Every hub endpoint returns {status, message, data}; callers want `data`.
export async function postForm(path, fields) {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    method: 'POST',
    body: toFormData(fields),
  })
  return unwrap(res)
}

// `base` targets a service other than the hub (e.g. the result manager).
export async function get(path, base = API_BASE_URL) {
  const res = await fetch(`${base}${path}`)
  return unwrap(res)
}

// Returns the raw Response — for endpoints that are not JSON (CSV export).
export async function postFormRaw(path, fields) {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    method: 'POST',
    body: toFormData(fields),
  })
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
