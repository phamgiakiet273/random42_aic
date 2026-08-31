import { SEARCH_TYPES } from '../api/search'
import { useSearchStore } from '../stores/searchStore'
import { useBaseSearchParams } from './useBaseSearchParams'

/** Builds the current query and runs it. Shared so the query panel and the
 *  filter inputs trigger exactly the same search. */
export function useRunSearch() {
  const store = useSearchStore()
  const baseParams = useBaseSearchParams()

  const buildParams = () => {
    const base = { ...baseParams(), searchType: store.searchType }
    if (store.searchType === SEARCH_TYPES.TEXT) return { ...base, text: store.text }
    if (store.searchType === SEARCH_TYPES.IMAGE)
      return { ...base, imagePath: store.imagePath }
    if (store.searchType === SEARCH_TYPES.TEMPORAL) {
      return {
        ...base,
        text: store.events.map((e) => e.trim()).filter(Boolean).join('. '),
        mainEventIndex: Math.min(store.mainEventIndex, store.events.length - 1),
      }
    }
    return { ...base, utilityFeature: store.utilityFeature }
  }

  const canRun =
    store.status !== 'loading' &&
    ((store.searchType === SEARCH_TYPES.TEXT && store.text.trim()) ||
      (store.searchType === SEARCH_TYPES.IMAGE && store.imagePath) ||
      (store.searchType === SEARCH_TYPES.TEMPORAL &&
        store.events.some((e) => e.trim())) ||
      store.searchType === SEARCH_TYPES.SCROLL)

  const run = async () => {
    if (!canRun) return
    try {
      await store.execute(buildParams())
    } catch {
      /* surfaced via store.error */
    }
  }

  return { run, canRun, buildParams }
}
