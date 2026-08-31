// Submission CSV rules (one row per prediction, max 100 rows, no header):
//   KIS   : <video_name>,<frame_idx>
//   Q&A   : <video_name>,<frame_idx>,<answer>   (answer max 100 chars)
//   TRAKE : <video_name>,<frame_1>,...,<frame_N>

export const MODES = ['kis', 'qa', 'trake']
export const MAX_ROWS = 100
export const MAX_ANSWER = 100

export const MODE_HINT = {
  kis: 'video_name, frame_idx',
  qa: 'video_name, frame_idx, answer (max 100 chars)',
  trake: 'video_name, frame_1, frame_2, ... frame_N (one row per prediction)',
}

/** Quoted fields may hold commas and newlines; "" is a literal quote. A naive
 *  split(',') loses everything after the first comma of an answer. */
export function parseCsv(text) {
  const rows = []
  let row = []
  let field = ''
  let inQuotes = false
  let started = false

  let s = String(text || '')
  if (s.charCodeAt(0) === 0xfeff) s = s.slice(1) // tolerate a BOM

  for (let i = 0; i < s.length; i++) {
    const ch = s[i]
    if (inQuotes) {
      if (ch === '"') {
        if (s[i + 1] === '"') {
          field += '"'
          i++
        } else inQuotes = false
      } else field += ch
      continue
    }
    if (ch === '"') {
      inQuotes = true
      started = true
    } else if (ch === ',') {
      row.push(field)
      field = ''
      started = true
    } else if (ch === '\n') {
      row.push(field)
      rows.push(row)
      row = []
      field = ''
      started = false
    } else if (ch !== '\r') {
      field += ch
      started = true
    }
  }
  if (started || field !== '' || row.length) {
    row.push(field)
    rows.push(row)
  }
  return rows.filter((r) => r.some((cell) => (cell || '').trim() !== ''))
}

/** Quote only when required, escaping " as "". */
export function csvField(value) {
  const s = value == null ? '' : String(value)
  return /[",\r\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s
}

/** Strip any .jpg/.avif suffix — the CSV carries a bare frame index. */
export function frameBase(id) {
  return String(id ?? '').trim().split('.')[0].trim()
}

/** Frames on disk are zero-padded to 5 digits. */
export function frameLabel(id) {
  const base = frameBase(id)
  return /^\d+$/.test(base) ? base.padStart(5, '0') : base
}

/** Frame ids compare as integers, so export without padding. */
export function frameForExport(id) {
  const base = frameBase(id)
  return /^\d+$/.test(base) ? String(parseInt(base, 10)) : base
}

export function cleanVideoName(name) {
  return String(name ?? '').trim().replace(/\.mp4$/i, '')
}

export function makeRow(videoName, frameIds, answer = '') {
  const frames = (Array.isArray(frameIds) ? frameIds : [frameIds])
    .map(frameBase)
    .filter(Boolean)
  return {
    id: `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`,
    video_name: cleanVideoName(videoName),
    frame_ids: frames,
    answer: answer == null ? '' : String(answer),
  }
}

/** Guess the mode from an uploaded file. null when ambiguous (three numeric
 *  columns is either a two-event TRAKE row or Q&A with a numeric answer). */
export function detectQueryMode(rows) {
  let maxCols = 0
  let sawTextThirdColumn = false
  rows.forEach((cols) => {
    maxCols = Math.max(maxCols, cols.length)
    if (cols.length >= 3 && !/^\d+$/.test(frameBase(cols[2]))) sawTextThirdColumn = true
  })
  if (sawTextThirdColumn) return 'qa'
  if (maxCols >= 4) return 'trake'
  if (maxCols === 2) return 'kis'
  return null
}

export function rowsFromCsv(text, mode) {
  const parsed = parseCsv(text)
  const detected = detectQueryMode(parsed)
  const effective = detected || mode
  const out = []
  parsed.forEach((cols) => {
    const cells = cols.map((c) => (c || '').trim())
    const videoName = cleanVideoName(cells[0])
    if (!videoName) return
    if (effective === 'trake') {
      const frames = cells.slice(1).filter(Boolean)
      if (frames.length) out.push(makeRow(videoName, frames))
    } else if (cells[1]) {
      // Anything past the answer column only happens on malformed input (an
      // unquoted answer containing commas) — stitch it back.
      const answer = effective === 'qa' ? cells.slice(2).join(',') : ''
      out.push(makeRow(videoName, [cells[1]], answer))
    }
  })
  return { rows: out, detected }
}

/** Live rule check shown above the grid. */
export function rowSummary(rows, mode) {
  const parts = [`${rows.length} row${rows.length === 1 ? '' : 's'}`]
  let warn = false
  if (rows.length > MAX_ROWS) {
    parts.push(`over the ${MAX_ROWS}-row limit`)
    warn = true
  }
  if (mode === 'qa') {
    const missing = rows.filter((r) => !(r.answer || '').trim()).length
    const tooLong = rows.filter((r) => (r.answer || '').trim().length > MAX_ANSWER).length
    if (missing) { parts.push(`${missing} without an answer`); warn = true }
    if (tooLong) { parts.push(`${tooLong} over ${MAX_ANSWER} chars`); warn = true }
  } else if (mode === 'trake') {
    const counts = new Set(rows.map((r) => r.frame_ids.length))
    if (counts.size > 1) {
      parts.push(`mixed event counts (${[...counts].sort((a, b) => a - b).join(', ')})`)
      warn = true
    } else if (counts.size === 1) parts.push(`${[...counts][0]} events per row`)
  }
  return { text: parts.join(' · '), warn }
}

/** Returns { csv, problems }. Caller decides whether to proceed. */
export function buildSubmissionCsv(rows, mode) {
  const problems = []
  const lines = []
  rows.forEach((result, i) => {
    const video = cleanVideoName(result.video_name)
    const frames = result.frame_ids.map(frameForExport).filter(Boolean)
    if (!video) problems.push(`Row ${i + 1}: missing video name`)
    if (frames.length === 0) problems.push(`Row ${i + 1}: no frame id`)

    if (mode === 'trake') {
      lines.push([video, ...frames].map(csvField).join(','))
    } else if (mode === 'qa') {
      const answer = (result.answer || '').trim()
      if (!answer) problems.push(`Row ${i + 1}: empty answer`)
      else if (answer.length > MAX_ANSWER)
        problems.push(`Row ${i + 1}: answer is ${answer.length} characters (max ${MAX_ANSWER})`)
      lines.push([video, frames[0] || '', answer].map(csvField).join(','))
    } else {
      lines.push([video, frames[0] || ''].map(csvField).join(','))
    }
  })
  if (mode === 'trake') {
    const counts = new Set(rows.map((r) => r.frame_ids.length))
    if (counts.size > 1) {
      problems.push(
        `Rows have different event counts (${[...counts].sort((a, b) => a - b).join(', ')}); every row must match the number of events the query asks for`,
      )
    }
  }
  // CRLF, no BOM, no header.
  return { csv: lines.join('\r\n') + (lines.length ? '\r\n' : ''), problems }
}
