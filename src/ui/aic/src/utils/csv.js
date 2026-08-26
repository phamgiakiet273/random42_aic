export function toResultCsv(records) {
  return records.map((r) => `${r.video_id},${r.keyframe_id}`).join('\n')
}

export function downloadCsvFile(filename, content) {
  const blob = new Blob([content], { type: 'text/csv' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}
