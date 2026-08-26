import { create } from 'zustand'

const DEFAULTS = {
  returnS2t: false,
  returnObject: false,
  frameClassFilter: [2, 3],
  autoTranslate: false,
  immediateRerun: false,
  topK: 100,
  resultsPerPage: 50,
  neighborFrameCount: 10,
  thumbnailSize: 200,
}

export const useSettingsStore = create((set) => ({
  ...DEFAULTS,
  update: (patch) => set(patch),
  toggleFrameClass: (value) =>
    set((state) => ({
      frameClassFilter: state.frameClassFilter.includes(value)
        ? state.frameClassFilter.filter((v) => v !== value)
        : [...state.frameClassFilter, value],
    })),
  reset: () => set(DEFAULTS),
}))
