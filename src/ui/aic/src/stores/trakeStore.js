import { create } from 'zustand'
export const useTrakeStore = create((set) => ({
  videoId: null,
  fps: 25,
  frames: [],
  markFrame: (videoId, fps, frameId) =>
    set((state) => {
      if (state.videoId !== videoId) {
        return { videoId, fps, frames: [frameId] }
      }
      if (state.frames.includes(frameId)) return state
      return { frames: [...state.frames, frameId].sort((a, b) => a - b) }
    }),
  removeFrame: (frameId) =>
    set((state) => ({ frames: state.frames.filter((f) => f !== frameId) })),
  clear: () => set({ videoId: null, frames: [] }),
}))
