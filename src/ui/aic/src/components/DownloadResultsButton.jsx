import { useState } from 'react'
import { Download, Loader2 } from 'lucide-react'
import { useSettingsStore } from '../stores/settingsStore'
import { useSearchStore } from '../stores/searchStore'
import { downloadResultCsv } from '../api/search'
import { videoStem } from '../api/media'
import { downloadCsvFile, toKisCsv } from '../utils/csv'

export default function DownloadResultsButton({ records }) {
  const downloadLimit = useSettingsStore((s) => s.downloadLimit)
  const serverSideExport = useSettingsStore((s) => s.serverSideExport)
  const lastParams = useSearchStore((s) => s.lastParams)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  async function handleDownload(format) {
    setError(null)
    // The server export re-runs the query, so it cannot honour frames excluded
    // only in the browser. Fall back to client-side whenever that would differ.
    const clientSideNeeded = !serverSideExport || !lastParams
    if (!clientSideNeeded) {
      setBusy(true)
      try {
        const { text, filename } = await downloadResultCsv(lastParams, {
          format,
          limit: downloadLimit,
        })
        downloadCsvFile(filename, text)
        return
      } catch (err) {
        setError(`Server export failed (${err.message}); exported from the browser instead.`)
      } finally {
        setBusy(false)
      }
    }

    const rows = records.slice(0, downloadLimit).map((r) => ({
      video: videoStem(r.video_name),
      keyframe: r.keyframe_id,
    }))
    downloadCsvFile('result_kis.csv', toKisCsv(rows))
  }

  return (
    <div className="flex items-center gap-2">
      <button
        type="button"
        className="btn btn-primary btn-sm gap-1.5"
        disabled={records.length === 0 || busy}
        onClick={() => handleDownload('kis')}
      >
        {busy ? <Loader2 size={16} className="animate-spin" /> : <Download size={16} />}
        Download CSV
      </button>
      {error && <span className="text-xs text-warning">{error}</span>}
    </div>
  )
}
