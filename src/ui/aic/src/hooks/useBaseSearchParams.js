import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { getVideoNames, getSubsets, effectiveSubsets } from '../api/search'
import { useSettingsStore } from '../stores/settingsStore'
import { useFiltersStore } from '../stores/filtersStore'
import { useExcludedFramesStore } from '../stores/excludedFramesStore'
import { useSearchStore } from '../stores/searchStore'

/**
 * The settings/filter half of a search request, shared by the query panel and
 * the per-card actions on each result so a card-initiated scroll honours the
 * same top-K, frame classes and exclusions as a typed query.
 */
export function useBaseSearchParams() {
  const model = useSearchStore((s) => s.model)
  const settings = useSettingsStore()
  const filters = useFiltersStore()
  const skipFrames = useExcludedFramesStore((s) => s.skipFrames)

  // Same queryKey as FiltersPanel, so this reuses the cached result rather than
  // refetching -- and deriving the prefixes here avoids writing them back into
  // a store from an effect, which is what caused an infinite render loop.
  const { data: videoNames } = useQuery({
    queryKey: ['videoNames', filters.batches],
    queryFn: () => getVideoNames(filters.batches),
    enabled: filters.batches.length > 0,
    staleTime: 5 * 60 * 1000,
  })

  const { data: subsetCatalog } = useQuery({
    queryKey: ['subsets'],
    queryFn: getSubsets,
    staleTime: 30 * 60 * 1000,
  })
  const checkedSubsets = effectiveSubsets(subsetCatalog, filters.subsets)

  const batchPrefixes = useMemo(
    () => (videoNames ?? []).filter((name) => !name.includes('_')),
    [videoNames],
  )

  return () => ({
    model,
    k: settings.topK,
    returnS2t: settings.returnS2t,
    frameClassFilter: settings.frameClassFilter,
    skipFrames: skipFrames(),
    sortToNews: settings.sortToNews,
    // Precedence: an explicit video selection wins; else the checked content
    // subsets scope the search (via `subset`, resolved to prefixes server-side);
    // else the ticked batches' prefixes. Subsets and batchPrefixes are not both
    // sent -- the server unions video_filter, which would re-widen to everything.
    videoFilter:
      filters.selectedVideos.length
        ? filters.selectedVideos.join(',')
        : checkedSubsets.length && subsetCatalog
          ? undefined
          : batchPrefixes.length
            ? batchPrefixes.join(',')
            : undefined,
    subset:
      !filters.selectedVideos.length && checkedSubsets.length && subsetCatalog
        ? checkedSubsets.join(',')
        : undefined,
    s2tFilter: filters.s2tFilter || undefined,
    timeIn: filters.timeIn || undefined,
    timeOut: filters.timeOut || undefined,
  })
}
