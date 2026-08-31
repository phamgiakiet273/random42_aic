import { create } from 'zustand'

export const useSelectionStore = create((set) => ({
  selected: new Set(),
  toggle: (key) =>
    set((state) => {
      const next = new Set(state.selected)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return { selected: next }
    }),
  selectMany: (keys) =>
    set((state) => {
      const next = new Set(state.selected)
      keys.forEach((k) => next.add(k))
      return { selected: next }
    }),
  clear: () => set({ selected: new Set() }),
}))
