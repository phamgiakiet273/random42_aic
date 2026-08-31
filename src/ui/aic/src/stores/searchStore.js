import { create } from 'zustand'
import { runSearch, SEARCH_TYPES, DEFAULT_MODEL } from '../api/search'
import { videoStem } from '../api/media'

// One record's stable identity across results, selection and exclusion.
export function recordKey(record) {
  if (!record) return ''
  return `${videoStem(record.video_name ?? record.video_id)}:${record.keyframe_id}`
}

/** A skip_frames entry. The backend excludes the whole shot
 *  (related_start_frame..related_end_frame) and keys on the video stem. */
export function toSkipFrame(record) {
  return {
    video_name: videoStem(record.video_name ?? record.video_id),
    related_start_frame: String(record.related_start_frame ?? record.keyframe_id),
    related_end_frame: String(record.related_end_frame ?? record.keyframe_id),
  }
}

const DEFAULT_QUERY = {
  searchType: SEARCH_TYPES.TEXT,
  model: DEFAULT_MODEL,
  text: '',
  imagePath: '',
  // One entry per temporal event; joined with ". " for the backend.
  events: [''],
  mainEventIndex: 0,
  utilityFeature: 'shot',
}

export const useSearchStore = create((set, get) => ({
  ...DEFAULT_QUERY,
  records: [],
  chains: null,
  // Key of the frame a card-initiated scroll was launched from, so the result
  // list can mark and scroll to it.
  originKey: null,
  status: 'idle', // idle | loading | success | error
  error: null,
  // The exact params the last successful search ran with, so CSV export and
  // "re-search on skip" can replay it without rebuilding them from the UI.
  lastParams: null,

  setQuery: (patch) => set(patch),
  resetQuery: () => set({ ...DEFAULT_QUERY }),

  async execute(params, { originKey = null } = {}) {
    const merged = { ...params }
    set({ status: 'loading', error: null, originKey })
    try {
      const { records, chains } = await runSearch(merged)
      set({ records, chains, status: 'success', lastParams: merged })
      return records
    } catch (err) {
      set({ status: 'error', error: err.message || String(err), records: [], chains: null })
      throw err
    }
  },

  /** Re-run the last search with an extra skip_frames entry appended. */
  async rerunWithSkips(skipFrames) {
    const last = get().lastParams
    if (!last) return
    return get().execute({ ...last, skipFrames })
  },

  clear: () =>
    set({ records: [], chains: null, status: 'idle', error: null, lastParams: null, originKey: null }),
}))
