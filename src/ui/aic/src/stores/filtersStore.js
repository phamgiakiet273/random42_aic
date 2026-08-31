import { create } from 'zustand'

const DEFAULTS = {
  videoSearch: '',
  selectedVideos: [],
  // Batch 0 only by default, matching the legacy default.
  batches: [0],
  excludedFrames: [],
  s2tFilter: '',
  timeIn: '',
  timeOut: '',
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
