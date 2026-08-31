import { create } from 'zustand'
import { recordKey, toSkipFrame } from './searchStore'

// Kept as the module's public name — components import { frameKey }.
export const frameKey = recordKey

export const useExcludedFramesStore = create((set, get) => ({
  excluded: new Set(),
  // Full records, so a skip can be sent to the backend and shown in the panel.
  records: [],

  exclude: (record) =>
    set((state) => {
      const key = frameKey(record)
      if (state.excluded.has(key)) return state
      const next = new Set(state.excluded)
      next.add(key)
      return { excluded: next, records: [...state.records, record] }
    }),

  remove: (key) =>
    set((state) => {
      const next = new Set(state.excluded)
      next.delete(key)
      return { excluded: next, records: state.records.filter((r) => frameKey(r) !== key) }
    }),

  /** skip_frames payload for the hub. */
  skipFrames: () => get().records.map(toSkipFrame),

  clear: () => set({ excluded: new Set(), records: [] }),
}))
