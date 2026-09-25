import { useQuery } from '@tanstack/react-query'
import { useRunSearch } from '../hooks/useRunSearch'
import { getVideoNames, getSubsets, effectiveSubsets, scopePrefixes, SEARCH_TYPES } from '../api/search'
import { useSearchStore } from '../stores/searchStore'
import { useFiltersStore } from '../stores/filtersStore'
import { useExcludedFramesStore, frameKey } from '../stores/excludedFramesStore'
import { videoStem } from '../api/media'
import { isEnter } from '../utils/keys'

const BATCHES = [0, 1]

// Module-level constant, not an inline `= []` default: a fresh array literal on
// every render is a new reference, which silently invalidates any hook that
// depends on it (that is what caused an infinite update loop here).
const NO_NAMES = []

export default function FiltersPanel() {
  const filters = useFiltersStore()
  const isBrowse = useSearchStore((s) => s.searchType) === SEARCH_TYPES.SCROLL
  const { run } = useRunSearch()
  const onEnter = (e) => {
    if (isEnter(e)) {
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

  const { data: subsetCatalog = {} } = useQuery({
    queryKey: ['subsets'],
    queryFn: getSubsets,
    staleTime: 30 * 60 * 1000,
  })
  const checkedSubsets = effectiveSubsets(subsetCatalog, filters.subsets)
  const toggleSubset = (name) =>
    filters.setSubsets(
      checkedSubsets.includes(name)
        ? checkedSubsets.filter((n) => n !== name)
        : [...checkedSubsets, name],
    )

  const batchPrefixes = videoNames.filter((name) => !name.includes('_'))
  const scope = scopePrefixes(subsetCatalog, checkedSubsets, filters.batches, batchPrefixes)
  const needle = filters.videoSearch.toLowerCase()
  const visibleVideoNames = videoNames.filter((name) => name.toLowerCase().includes(needle))

  return (
    <div className="card bg-base-100 shadow-sm">
      <div className="card-body gap-4">
        <h2 className="card-title text-base">Filters</h2>

        <div>
          <p className="text-xs uppercase tracking-wide text-base-content/60 mb-1">
            Batch
          </p>
          <div className="flex gap-3">
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
          {isError && (
            <p className="text-[10px] text-warning mt-1">
              Batch scoping is OFF: the video-name list could not be loaded, so
              searches will span every batch.
            </p>
          )}
        </div>

        <div>
          <div className="flex items-center justify-between mb-1">
            <p className="text-xs uppercase tracking-wide text-base-content/60">Content</p>
            <span className="flex gap-1">
              {/* null = the catalog's default-checked content (subsets.json) */}
              <button type="button" className="btn btn-ghost btn-xs" title="Back to the default content" onClick={() => filters.setSubsets(null)}>
                default
              </button>
              <button type="button" className="btn btn-ghost btn-xs" onClick={() => filters.setSubsets(Object.keys(subsetCatalog))}>
                all
              </button>
              <button type="button" className="btn btn-ghost btn-xs" onClick={() => filters.setSubsets([])}>
                none
              </button>
            </span>
          </div>
          <div className="grid grid-cols-2 gap-x-2">
            {Object.entries(subsetCatalog).map(([name, info]) => (
              <label
                key={name}
                className="label cursor-pointer justify-start gap-2 px-1 py-0.5"
                title={info.desc}
              >
                <input
                  type="checkbox"
                  className="checkbox checkbox-xs"
                  checked={checkedSubsets.includes(name)}
                  onChange={() => toggleSubset(name)}
                />
                <span className="label-text text-xs">{info.label || name}</span>
              </label>
            ))}
          </div>
          {scope && scope.length === 0 ? (
            <p className="text-[10px] text-warning mt-1">
              None of the ticked content is in the ticked batch{filters.batches.length === 1 ? '' : 'es'}: searches find nothing.
            </p>
          ) : (
            <p className="text-[10px] text-base-content/50 mt-1">
              {checkedSubsets.length
                ? `Searching: ${checkedSubsets.join(', ')}` +
                  (filters.batches.length === 1 ? `, batch ${filters.batches[0]} only` : '') +
                  '. Unchecked content is excluded.'
                : 'No content type checked — searching the ticked batches.'}
            </p>
          )}
        </div>

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
          <div className="border border-base-300 rounded-lg max-h-40 overflow-y-auto" aria-busy={isLoading}>
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
          {filters.selectedVideos.length > 0 && (
            <p className="text-[10px] text-base-content/50 mt-2">
              Scoped to {filters.selectedVideos.length} selected video(s): overrides content and batch.
            </p>
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
          {/* Browse only: the backend applies the range to Browse alone, and in
              frame numbers (a timecode made it fail). */}
          {isBrowse && (
            <div className="flex gap-2">
              <input
                type="text"
                inputMode="numeric"
                placeholder="From frame"
                title="Browse only: first frame number (inclusive)"
                className="input input-bordered input-sm flex-1"
                value={filters.timeIn}
                onChange={(e) => filters.update({ timeIn: e.target.value.replace(/\D/g, '') })}
                onKeyDown={onEnter}
              />
              <input
                type="text"
                inputMode="numeric"
                placeholder="To frame"
                title="Browse only: last frame number (inclusive)"
                className="input input-bordered input-sm flex-1"
                value={filters.timeOut}
                onChange={(e) => filters.update({ timeOut: e.target.value.replace(/\D/g, '') })}
                onKeyDown={onEnter}
              />
            </div>
          )}
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

        <button type="button" className="btn btn-ghost btn-sm mt-2" onClick={() => filters.reset()}>
          Reset all filters
        </button>
      </div>
    </div>
  )
}
