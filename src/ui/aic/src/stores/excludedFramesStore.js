import { create } from 'zustand'
export function frameKey(record) {
  return `${record.video_id}:${record.frame_name ?? record.keyframe_id ?? record.id}`
}

export const useExcludedFramesStore = create((set) => ({
  excluded: new Set(),
  exclude: (record) =>
    set((state) => {
      const next = new Set(state.excluded)
      next.add(frameKey(record))
      return { excluded: next }
    }),
  clear: () => set({ excluded: new Set() }),
}))
