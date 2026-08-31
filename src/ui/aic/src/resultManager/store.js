import { create } from 'zustand'
import { makeRow, frameBase, cleanVideoName } from './csv'

const DEFAULTS = {
  mode: 'kis',
  rows: [],
  selected: new Set(),
  lastSelectedIndex: null,
  thumbnailSize: 180,
  filename: 'query-1',
  // Frames marked off the video player, pending insertion as a TRAKE row.
  marks: [],
  markVideo: '',
}

export const useResultStore = create((set, get) => ({
  ...DEFAULTS,

  setMode: (mode) => set({ mode }),
  update: (patch) => set(patch),
  reset: () => set({ ...DEFAULTS, selected: new Set() }),

  /** Splice rows in, keeping the selection anchored to the same items. */
  insertRows: (newRows, insertIndex) =>
    set((state) => {
      const rows = [...state.rows]
      rows.splice(insertIndex, 0, ...newRows)
      const selected = new Set()
      state.selected.forEach((i) =>
        selected.add(i >= insertIndex ? i + newRows.length : i),
      )
      let last = state.lastSelectedIndex
      if (last !== null && last >= insertIndex) last += newRows.length
      return { rows, selected, lastSelectedIndex: last }
    }),

  replaceRows: (rows) => set({ rows, selected: new Set(), lastSelectedIndex: null }),

  moveRow: (from, to) =>
    set((state) => {
      const rows = [...state.rows]
      const [moved] = rows.splice(from, 1)
      rows.splice(to, 0, moved)
      return { rows, selected: new Set(), lastSelectedIndex: null }
    }),

  updateRow: (index, patch) =>
    set((state) => ({
      rows: state.rows.map((r, i) => (i === index ? { ...r, ...patch } : r)),
    })),

  toggleSelected: (index, shiftKey) =>
    set((state) => {
      const selected = new Set(state.selected)
      if (shiftKey && state.lastSelectedIndex !== null) {
        const [lo, hi] = [state.lastSelectedIndex, index].sort((a, b) => a - b)
        for (let i = lo; i <= hi; i++) selected.add(i)
      } else if (selected.has(index)) selected.delete(index)
      else selected.add(index)
      return { selected, lastSelectedIndex: index }
    }),

  selectAll: () => set((state) => ({ selected: new Set(state.rows.map((_, i) => i)) })),
  clearSelection: () => set({ selected: new Set(), lastSelectedIndex: null }),

  deleteSelected: () =>
    set((state) => ({
      rows: state.rows.filter((_, i) => !state.selected.has(i)),
      selected: new Set(),
      lastSelectedIndex: null,
    })),

  /** Bulk-fill answers into the rows themselves, so the grid shows what the
   *  CSV will contain. An empty band leaves a row's existing answer alone. */
  applyAnswers: ({ single, bands }) =>
    set((state) => ({
      rows: state.rows.map((row, index) => {
        if (single != null) return { ...row, answer: single }
        const value =
          index === 0 ? bands.row1
          : index < 5 ? bands.row2_5
          : index < 20 ? bands.row6_20
          : index < 50 ? bands.row21_50
          : bands.row51_end
        return value ? { ...row, answer: value } : row
      }),
    })),

  addMark: (video, frameId) =>
    set((state) => {
      const v = cleanVideoName(video)
      if (state.markVideo !== v) return { markVideo: v, marks: [frameId] }
      if (state.marks.includes(frameId)) return state
      return { marks: [...state.marks, frameId].sort((a, b) => a - b) }
    }),
  removeMark: (frameId) =>
    set((state) => ({ marks: state.marks.filter((f) => f !== frameId) })),
  clearMarks: () => set({ marks: [], markVideo: '' }),

  /** Turn the marked frames into one TRAKE row. */
  addRowFromMarks: (insertIndex) => {
    const { markVideo, marks, insertRows, rows } = get()
    if (!markVideo || marks.length === 0) return false
    insertRows([makeRow(markVideo, marks.map(String))], insertIndex ?? rows.length)
    set({ marks: [], markVideo: '' })
    return true
  },

  /** Frames from a start..end range at a fixed interval. TRAKE gets one row
   *  holding the sequence; KIS/Q&A get one row per frame. */
  addRange: ({ videoName, start, end, interval, insertIndex }) => {
    const { mode, insertRows, rows } = get()
    const frames = []
    for (let f = start; f <= end; f += interval) frames.push(String(f).padStart(5, '0'))
    if (!frames.length) return 0
    const newRows =
      mode === 'trake'
        ? [makeRow(videoName, frames)]
        : frames.map((f) => makeRow(videoName, [f]))
    insertRows(newRows, insertIndex ?? rows.length)
    return frames.length
  },

  addManual: ({ videoName, frameInput, insertIndex }) => {
    const { mode, insertRows, rows } = get()
    const frames = frameInput.split(/[,\s]+/).map(frameBase).filter(Boolean)
    if (!frames.length) return { ok: false, error: 'Enter at least one frame ID' }
    if (mode !== 'trake' && frames.length > 1) {
      return {
        ok: false,
        error: `${mode.toUpperCase()} rows hold a single frame. Switch to TRAKE for an event sequence.`,
      }
    }
    insertRows([makeRow(videoName, frames)], insertIndex ?? rows.length)
    return { ok: true }
  },
}))
