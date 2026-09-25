import { SEARCH_TYPES } from '../api/search'
import { useSearchStore } from '../stores/searchStore'
import { useSettingsStore } from '../stores/settingsStore'
import { translateQuery, useTranslateStore } from '../api/translateQuery'
import { useBaseSearchParams } from './useBaseSearchParams'

/** Builds the current query and runs it. Shared so the query panel and the
 *  filter inputs trigger exactly the same search. */
export function useRunSearch() {
  const store = useSearchStore()
  const baseParams = useBaseSearchParams()
  const autoTranslate = useSettingsStore((s) => s.autoTranslate)
  const translating = useTranslateStore((s) => s.busy)

  // reads the store at call time: Auto Translate rewrites the query just before
  const buildParams = () => {
    const q = useSearchStore.getState()
    const base = { ...baseParams(), searchType: q.searchType }
    if (q.searchType === SEARCH_TYPES.TEXT) return { ...base, text: q.text }
    if (q.searchType === SEARCH_TYPES.IMAGE)
      return { ...base, imagePath: q.imagePath }
    if (q.searchType === SEARCH_TYPES.TEMPORAL) {
      // The backend splits the text on '.', so a '.' INSIDE an event ("2.5 kg")
      // would make extra events; blank events are dropped, so the main index is
      // re-counted over the events actually sent.
      const events = q.events
        .map((e, i) => ({ text: e.trim().replace(/\./g, ','), i }))
        .filter((e) => e.text)
      return {
        ...base,
        text: events.map((e) => e.text).join('. '),
        mainEventIndex: Math.max(0, events.findIndex((e) => e.i === q.mainEventIndex)),
      }
    }
    return { ...base, utilityFeature: q.utilityFeature }
  }

  const canRun =
    store.status !== 'loading' &&
    !translating &&
    ((store.searchType === SEARCH_TYPES.TEXT && store.text.trim()) ||
      (store.searchType === SEARCH_TYPES.IMAGE && store.imagePath) ||
      (store.searchType === SEARCH_TYPES.TEMPORAL &&
        store.events.some((e) => e.trim())) ||
      store.searchType === SEARCH_TYPES.SCROLL)

  const run = async () => {
    if (!canRun) return
    // Settings -> Auto Translate: Vietnamese boxes become English first (a failure
    // stops the search and shows why under the query title)
    if (autoTranslate && !(await translateQuery())) return
    try {
      await useSearchStore.getState().execute(buildParams())
    } catch {
      /* surfaced via store.error */
    }
  }

  return { run, canRun, buildParams }
}
