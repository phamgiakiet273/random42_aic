import { create } from 'zustand'

const DEFAULTS = {
  videoSearch: '',
  selectedVideos: [],
  // Both batches by default (user, 2026-09-24): batch 1 is the 2026 data (M/N/S),
  // and the video picker only lists ticked batches.
  batches: [0, 1],
  excludedFrames: [],
  s2tFilter: '',
  timeIn: '',
  timeOut: '',
  // null = fall back to the catalog's default-checked subsets (subsets.json
  // "default"). An array = the user's explicit checkbox selection.
  subsets: null,
}

export const useFiltersStore = create((set) => ({
  ...DEFAULTS,
  update: (patch) => set(patch),
  toggleBatch: (value) =>
    set((state) => ({
      batches: state.batches.includes(value)
        ? state.batches.filter((v) => v !== value)
        : [...state.batches, value],
    })),
  setSubsets: (names) => set({ subsets: names }),
  toggleVideo: (name) =>
    set((state) => ({
      selectedVideos: state.selectedVideos.includes(name)
        ? state.selectedVideos.filter((v) => v !== name)
        : [...state.selectedVideos, name],
    })),
  removeExcludedFrame: (id) =>
    set((state) => ({
      excludedFrames: state.excludedFrames.filter((frame) => frame.id !== id),
    })),
  reset: () => set(DEFAULTS),
}))
