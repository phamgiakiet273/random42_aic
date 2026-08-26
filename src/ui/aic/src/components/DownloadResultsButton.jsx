import { Download } from 'lucide-react'
import { useSettingsStore } from '../stores/settingsStore'
import { toResultCsv, downloadCsvFile } from '../utils/csv'
import { cleanFrameName } from '../utils/frameName'

export default function DownloadResultsButton({ records }) {
  const downloadLimit = useSettingsStore((s) => s.downloadLimit)

  const handleDownload = () => {
    const rows = records.slice(0, downloadLimit).map((r) => ({
      video_id: r.video_id,
      keyframe_id: cleanFrameName(r.frame_name) || r.keyframe_id,
    }))
    downloadCsvFile('result.csv', toResultCsv(rows))
  }

  return (
    <button
      type="button"
      className="btn btn-primary btn-sm gap-1.5"
      disabled={records.length === 0}
      onClick={handleDownload}
    >
      <Download size={16} />
      Download CSV
    </button>
  )
}
