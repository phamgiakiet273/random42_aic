// Vietnamese -> English for the query boxes: the query panel's T button, and Settings ->
// Auto Translate before every search. The server translates offline (VinAI model in the
// util service). The box is rewritten in place, so it shows what gets searched.
import { create } from 'zustand'
import { SEARCH_TYPES, translate } from './search'
import { useSearchStore } from '../stores/searchStore'
import { hasVietnamese } from '../utils/vietnamese'

export const useTranslateStore = create(() => ({ busy: false, error: null }))

/** Translate the Text query, or every Temporal event, that has Vietnamese in it.
 *  -> true when done or nothing to do; false on failure (message in the store). */
export async function translateQuery() {
  const before = useSearchStore.getState()
  const isText = before.searchType === SEARCH_TYPES.TEXT
  if (!isText && before.searchType !== SEARCH_TYPES.TEMPORAL) return true
  const inputs = isText ? [before.text] : before.events
  if (!inputs.some(hasVietnamese)) return true
  useTranslateStore.setState({ busy: true, error: null })
  try {
    const outputs = await Promise.all(inputs.map((t) => (hasVietnamese(t) ? translate(t) : t)))
    const now = useSearchStore.getState()
    if (now.searchType !== before.searchType || (isText ? now.text !== before.text : now.events !== before.events)) {
      useTranslateStore.setState({ error: 'The query changed while translating: press T again' })
      return false
    }
    now.setQuery(isText ? { text: outputs[0] } : { events: outputs })
    return true
  } catch (e) {
    useTranslateStore.setState({ error: `Translation failed: ${e?.message || e}` })
    return false
  } finally {
    useTranslateStore.setState({ busy: false })
  }
}
