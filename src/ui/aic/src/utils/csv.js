// Submission CSV shape, matching what the backend's /hub/download emits and
// what last year's tooling consumed. No header row.

/** KIS: one `video,keyframe` per row. */
export function toKisCsv(rows) {
  return rows.map((r) => `${r.video},${r.keyframe}`).join('\n') + (rows.length ? '\n' : '')
}

export function downloadCsvFile(filename, content) {
  const blob = new Blob([content], { type: 'text/csv' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}
