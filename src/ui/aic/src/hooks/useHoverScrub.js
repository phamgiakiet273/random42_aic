import { useCallback, useEffect, useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { getNeighboringFrames } from '../api/search'
import { videoStem } from '../api/media'

// Hover-scrub on a result card: cursor on the right half plays the next keyframes,
// on the left half the previous ones, one step every STEP_MS; leaving the card (or
// moving onto one of its buttons) snaps back to the result's own frame. The buttons
// act on the RESULT frame, so the preview never runs while the cursor is on them.
const DWELL_MS = 200 // a cursor just passing over a card does nothing
const STEP_MS = 250
const SPAN = 200 // keyframes fetched each side of the result frame
const CONTROLS = 'button, a, input, select, textarea, label, [role="button"]'

// url -> Promise<boolean> (loaded?), shared by all cards: a step only shows a
// frame once it has loaded, so a slow link pauses the preview instead of blanking it.
const loaded = new Map()
function preload(url) {
  let p = loaded.get(url)
  if (!p) {
    if (loaded.size > 3000) loaded.clear()
    p = new Promise((resolve) => {
      const im = new Image()
      im.onload = () => resolve(true)
      im.onerror = () => resolve(false)
      im.src = url
    })
    loaded.set(url, p)
  }
  return p
}

const frameOf = (path) => path.split('/').pop().split('.')[0]

/** -> { preview: {url, frame, dir} | null, onMouseMove, onMouseLeave } */
export function useHoverScrub(record, imageBase) {
  const queryClient = useQueryClient()
  const [preview, setPreview] = useState(null)
  const st = useRef({ alive: false, dir: 0, dwell: null, timer: null, list: null, idx: -1, busy: false })

  const stop = useCallback(() => {
    const s = st.current
    clearTimeout(s.dwell)
    clearInterval(s.timer)
    Object.assign(s, { alive: false, dir: 0, dwell: null, timer: null, list: null, idx: -1, busy: false })
    setPreview(null)
  }, [])

  // a new result in this card, or the card going away, ends any preview
  useEffect(() => stop, [record, stop])

  const step = useCallback(async () => {
    const s = st.current
    if (!s.alive || !s.list || s.busy || !s.dir) return
    const j = s.idx + s.dir
    if (j < 0 || j >= s.list.length) return // hold on the first / last keyframe
    const path = s.list[j] // null = the result's own frame
    const url = path == null ? null : `${imageBase}/${path}`
    s.busy = true
    const ok = url ? await preload(url) : true
    s.busy = false
    if (!s.alive) return
    s.idx = j // a frame that failed to load is stepped over
    if (ok) setPreview(path == null ? null : { url, frame: frameOf(path), dir: s.dir })
    for (const d of [1, 2]) {
      const ahead = s.list[j + s.dir * d]
      if (ahead) preload(`${imageBase}/${ahead}`)
    }
  }, [imageBase])

  const start = useCallback(async () => {
    const s = st.current
    const video = videoStem(record.video_name)
    const frame = String(record.keyframe_id)
    let data
    try {
      data = await queryClient.fetchQuery({
        queryKey: ['scrubNeighbors', video, frame],
        queryFn: () => getNeighboringFrames(video, frame, SPAN),
        staleTime: Infinity,
      })
    } catch {
      return // no neighbours (util service down): the card just stays still
    }
    if (!s.alive) return
    const prev = data?.prev_frames || []
    const next = data?.next_frames || []
    s.list = [...prev, null, ...next]
    s.idx = prev.length
    s.timer = setInterval(step, STEP_MS)
    step()
  }, [queryClient, record, step])

  const onMouseMove = useCallback(
    (e) => {
      const s = st.current
      if (!imageBase || !record) return
      if (e.target.closest?.(CONTROLS)) {
        if (s.alive || s.dwell) stop()
        return
      }
      const box = e.currentTarget.getBoundingClientRect()
      s.dir = e.clientX - box.left >= box.width / 2 ? 1 : -1
      if (!s.alive && !s.dwell) {
        s.dwell = setTimeout(() => {
          s.dwell = null
          s.alive = true
          start()
        }, DWELL_MS)
      }
    },
    [imageBase, record, start, stop],
  )

  return { preview, onMouseMove, onMouseLeave: stop }
}
