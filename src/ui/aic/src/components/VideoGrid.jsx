import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchMediaConfig } from '../api/media'
import { useSearchStore, recordKey } from '../stores/searchStore'
import { useSettingsStore } from '../stores/settingsStore'
import { useExcludedFramesStore } from '../stores/excludedFramesStore'
import Thumbnail from './Thumbnail'
import FrameDetailModal from './FrameDetailModal'
import { useSubmissionStore } from '../stores/submissionStore'
import Pagination from './Pagination'
import DownloadResultsButton from './DownloadResultsButton'
import TemporalChainRow from './TemporalChainRow'

export default function VideoGrid() {
  const viewer = useSubmissionStore((s) => s.viewer)
  const openViewer = useSubmissionStore((s) => s.openViewer)
  const closeViewer = useSubmissionStore((s) => s.closeViewer)
  const [page, setPage] = useState(1)

  const records = useSearchStore((s) => s.records)
  const chains = useSearchStore((s) => s.chains)
  const status = useSearchStore((s) => s.status)
  const error = useSearchStore((s) => s.error)
  const resultsPerPage = useSettingsStore((s) => s.resultsPerPage)
  const thumbnailSize = useSettingsStore((s) => s.thumbnailSize)
  const excluded = useExcludedFramesStore((s) => s.excluded)
  const lastParams = useSearchStore((s) => s.lastParams)
  const originKey = useSearchStore((s) => s.originKey)

  // The layout rule for building media URLs; fetched once and cached.
  const { data: mediaConfig, isError: mediaConfigFailed } = useQuery({
    queryKey: ['mediaConfig'],
    queryFn: fetchMediaConfig,
    staleTime: Infinity,
  })

  const [prevPerPage, setPrevPerPage] = useState(resultsPerPage)
  if (resultsPerPage !== prevPerPage) {
    setPrevPerPage(resultsPerPage)
    setPage(1)
  }

  const visible = records.filter((r) => !excluded.has(recordKey(r)))

  // Temporal results paginate by chain (one row each), everything else by frame.
  const isTemporal = Array.isArray(chains) && chains.length > 0
  const visibleChains = isTemporal
    ? chains.filter((chain) => chain.some((f) => !excluded.has(recordKey(f))))
    : []
  const units = isTemporal ? visibleChains : visible
  const perPage = isTemporal ? Math.max(1, Math.floor(resultsPerPage / 10)) : resultsPerPage
  const totalPages = Math.max(1, Math.ceil(units.length / perPage))

  // Every NEW search starts on page 1 (it used to reset only when the result
  // COUNT changed, and most searches return exactly top-K), except a card's
  // "browse this shot" / "similar frames", which opens on the page holding the
  // card it started from.
  const [prevSearch, setPrevSearch] = useState(lastParams)
  if (lastParams !== prevSearch) {
    setPrevSearch(lastParams)
    const at = originKey && !isTemporal ? visible.findIndex((r) => recordKey(r) === originKey) : -1
    setPage(at >= 0 ? Math.floor(at / perPage) + 1 : 1)
  }
  const current = Math.min(page, totalPages) // exclusions can shrink the list

  if (status === 'loading') {
    return (
      <div className="flex justify-center p-16">
        <span className="loading loading-spinner loading-lg" />
      </div>
    )
  }

  if (status === 'error') {
    return <div className="alert alert-error">Search failed: {error}</div>
  }

  if (status === 'idle') {
    return (
      <div className="hero bg-base-100 rounded-lg py-16">
        <div className="hero-content text-center text-base-content/60">
          <div>
            <p className="text-lg font-medium">No search yet</p>
            <p className="text-sm">Enter a query on the left to search the keyframe index.</p>
          </div>
        </div>
      </div>
    )
  }

  const pageItems = units.slice((current - 1) * perPage, current * perPage)

  return (
    <div className="flex flex-col gap-4">
      {mediaConfigFailed && (
        <div className="alert alert-warning text-sm py-2">
          Could not load media config from the hub — thumbnails will not render.
        </div>
      )}

      <div className="flex items-center justify-between gap-2 flex-wrap">
        <div className="flex items-center gap-3">
          <DownloadResultsButton records={visible} />
          <span className="text-xs text-base-content/60">
            {isTemporal
              ? `${visibleChains.length} temporal result${visibleChains.length === 1 ? '' : 's'}`
              : `${visible.length} result${visible.length === 1 ? '' : 's'}`}
            {!isTemporal &&
              records.length !== visible.length &&
              ` (${records.length - visible.length} excluded)`}
          </span>
        </div>
        <Pagination
          page={current}
          totalPages={totalPages}
          onPrev={() => setPage(Math.max(1, current - 1))}
          onNext={() => setPage(Math.min(totalPages, current + 1))}
        />
      </div>

      {isTemporal ? (
        <div className="flex flex-col gap-4">
          {pageItems.map((chain, i) => (
            <TemporalChainRow
              key={`chain-${(current - 1) * perPage + i}`}
              chain={chain}
              rank={(current - 1) * perPage + i + 1}
              mediaConfig={mediaConfig}
              onSelect={(frame) => openViewer(frame)}
            />
          ))}
        </div>
      ) : (
        <div
          className="grid gap-4"
          style={{ gridTemplateColumns: `repeat(auto-fill, minmax(min(${thumbnailSize}px, 45vw), 1fr))` }}
        >
          {pageItems.map((record, i) => (
            <Thumbnail
              key={`${recordKey(record)}:${record.chainId ?? ''}:${i}`}
              record={record}
              mediaConfig={mediaConfig}
              index={(current - 1) * perPage + i + 1}
              onClick={() => openViewer(record)}
            />
          ))}
        </div>
      )}

      {units.length === 0 && (
        <p className="text-center text-sm text-base-content/60 py-8">
          {records.length === 0 ? 'No results.' : 'Every result was excluded.'}
        </p>
      )}

      {/* keyed per open: every open is a fresh viewer (tab, marks, answer) */}
      <FrameDetailModal
        key={viewer?.nonce ?? 'closed'}
        record={viewer?.record ?? null}
        initialTab={viewer?.tab}
        initialMarks={viewer?.marks}
        mediaConfig={mediaConfig}
        onClose={closeViewer}
      />
    </div>
  )
}
