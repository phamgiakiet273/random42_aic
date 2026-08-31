import { create } from 'zustand'

const DEFAULTS = {
  returnS2t: true,
  // `returnObject` is gone: doc comment [k]. The field was empty on all
  // 872,631 indexed points, so the backend no longer returns or accepts it.
  frameClassFilter: [],
  sortToNews: true,
  autoTranslate: false,
  immediateRerun: false,
  topK: 100,
  resultsPerPage: 50,
  neighborFrameCount: 10,
  thumbnailSize: 220,
  downloadLimit: 100,
  // Server-rendered CSV (GET /hub/download) vs building it in the browser.
  serverSideExport: true,
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
