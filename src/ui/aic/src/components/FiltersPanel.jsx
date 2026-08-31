import { useQuery } from '@tanstack/react-query'
import { useRunSearch } from '../hooks/useRunSearch'
import { getVideoNames } from '../api/search'
import { useFiltersStore } from '../stores/filtersStore'
import { useExcludedFramesStore, frameKey } from '../stores/excludedFramesStore'
import { videoStem } from '../api/media'

const BATCHES = [0, 1]

// Module-level constant, not an inline `= []` default: a fresh array literal on
// every render is a new reference, which silently invalidates any hook that
// depends on it (that is what caused an infinite update loop here).
const NO_NAMES = []

export default function FiltersPanel() {
  const filters = useFiltersStore()
  const { run } = useRunSearch()
  const onEnter = (e) => {
    if (e.key === 'Enter') {
      e.preventDefault()
      run()
    }
  }
  const excludedRecords = useExcludedFramesStore((s) => s.records)
  const removeExcluded = useExcludedFramesStore((s) => s.remove)
  const clearExcluded = useExcludedFramesStore((s) => s.clear)

  // Returns batch prefixes ("L21") alongside full names ("L21_V001"). Both are
  // useful: video_filter matches by prefix, so selecting "L21" scopes the
  // search to that whole batch prefix.
  const {
    data: videoNames = NO_NAMES,
    isLoading,
    isError,
  } = useQuery({
    queryKey: ['videoNames', filters.batches],
    queryFn: () => getVideoNames(filters.batches),
    enabled: filters.batches.length > 0,
    staleTime: 5 * 60 * 1000,
  })

  const batchPrefixes = videoNames.filter((name) => !name.includes('_'))
  const needle = filters.videoSearch.toLowerCase()
  const visibleVideoNames = videoNames.filter((name) => name.toLowerCase().includes(needle))

  return (
    <div className="card bg-base-100 shadow-sm">
      <div className="card-body gap-4">
        <h2 className="card-title text-base">Filters</h2>

        <div>
          <p className="text-xs uppercase tracking-wide text-base-content/60 mb-1">
            Included videos
            {filters.selectedVideos.length > 0 && ` (${filters.selectedVideos.length})`}
          </p>
          <input
            type="text"
            placeholder="Search videos..."
            className="input input-bordered input-sm w-full mb-2"
            value={filters.videoSearch}
            onChange={(e) => filters.update({ videoSearch: e.target.value })}
          />
          <div className="border border-base-300 rounded-lg max-h-40 overflow-y-auto">
            {isLoading && <p className="text-xs p-2 text-base-content/50">Loading…</p>}
            {isError && (
              <p className="text-xs p-2 text-error">
                Could not reach the util service for video names.
              </p>
            )}
            {!isLoading &&
              !isError &&
              visibleVideoNames.map((name) => (
                <label
                  key={name}
                  className="label cursor-pointer justify-start gap-2 px-2 py-1 hover:bg-base-200"
                >
                  <input
                    type="checkbox"
                    className="checkbox checkbox-xs"
                    checked={filters.selectedVideos.includes(name)}
                    onChange={() => filters.toggleVideo(name)}
                  />
                  <span className="label-text text-xs">{name}</span>
                </label>
              ))}
          </div>
          {isError ? (
            <p className="text-[10px] text-warning mt-2">
              Batch scoping is OFF: the video-name list could not be loaded, so
              searches will span every batch.
            </p>
          ) : (
            <p className="text-[10px] text-base-content/50 mt-2">
              {filters.selectedVideos.length
                ? `Scoped to ${filters.selectedVideos.length} selected video(s).`
                : batchPrefixes.length
                  ? `Scoping searches to: ${batchPrefixes.join(', ')}`
                  : 'Loading batch scope…'}
            </p>
          )}
          <div className="flex gap-3 mt-1">
            {BATCHES.map((value) => (
              <label key={value} className="label cursor-pointer gap-1">
                <input
                  type="checkbox"
                  className="checkbox checkbox-sm"
                  checked={filters.batches.includes(value)}
                  onChange={() => filters.toggleBatch(value)}
                />
                <span className="label-text">Batch {value}</span>
              </label>
            ))}
          </div>
        </div>

        <div>
          <div className="flex items-center justify-between mb-1">
            <p className="text-xs uppercase tracking-wide text-base-content/60">
              Excluded shots
            </p>
            {excludedRecords.length > 0 && (
              <button type="button" className="btn btn-ghost btn-xs" onClick={clearExcluded}>
                Clear
              </button>
            )}
          </div>
          {excludedRecords.length === 0 ? (
            <p className="text-xs text-base-content/50">
              Excluding a frame hides its whole shot from future searches.
            </p>
          ) : (
            <ul className="text-xs flex flex-col gap-1 max-h-32 overflow-y-auto">
              {excludedRecords.map((record) => (
                <li
                  key={frameKey(record)}
                  className="flex items-center justify-between bg-base-200 rounded px-2 py-1"
                >
                  <span className="truncate">
                    {videoStem(record.video_name)} · {record.keyframe_id}
                  </span>
                  <button
                    type="button"
                    className="btn btn-ghost btn-xs"
                    onClick={() => removeExcluded(frameKey(record))}
                    aria-label="Un-exclude"
                  >
                    ×
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div>
          <p className="text-xs uppercase tracking-wide text-base-content/60 mb-1">
            Other filters
          </p>
          <div className="relative mb-2">
            <input
              type="text"
              placeholder="Transcript (S2T) contains..."
              className={`input input-bordered input-sm w-full ${filters.s2tFilter ? 'input-primary pr-16' : ''}`}
              value={filters.s2tFilter}
              onChange={(e) => filters.update({ s2tFilter: e.target.value })}
              onKeyDown={onEnter}
            />
            {filters.s2tFilter && (
              <span className="badge badge-primary badge-xs absolute right-2 top-1/2 -translate-y-1/2">
                active
              </span>
            )}
          </div>
          {filters.s2tFilter && (
            <p className="text-[10px] text-base-content/50 -mt-1 mb-2">
              Applied on the next search. Result count stays at top-K; the frames
              returned are the ones whose transcript matches.
            </p>
          )}
          <div className="flex gap-2">
            <input
              type="text"
              placeholder="Time in"
              className="input input-bordered input-sm flex-1"
              value={filters.timeIn}
              onChange={(e) => filters.update({ timeIn: e.target.value })}
              onKeyDown={onEnter}
            />
            <input
              type="text"
              placeholder="Time out"
              className="input input-bordered input-sm flex-1"
              value={filters.timeOut}
              onChange={(e) => filters.update({ timeOut: e.target.value })}
              onKeyDown={onEnter}
            />
          </div>
        </div>

        <button type="button" className="btn btn-ghost btn-sm mt-2" onClick={() => filters.reset()}>
          Reset all filters
        </button>
      </div>
    </div>
  )
}
