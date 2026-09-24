// Frame number <-> time in the original video.
//
// Our frame numbers are OpenCV's decode counter. On almost every video that is
// exactly time = frame / fps. On 122 N traffic cams it is not (OpenCV skips
// corrupt frames and/or the frame rate varies: up to ~20 s off), so the real time
// of every frame is published next to the keyframes:
//   <image base>/1/fps/frame_ms/index.json      {"videos": [stems]}
//   <image base>/1/fps/frame_ms/<video>.json    {"ms": [real ms of frame 0, 1, ...]}
// (batch1/frame_ms/). DRES wants "the time the frame appears in the original
// video", so a submission uses the table whenever the video has one.
import { fetchMediaConfig, videoStem } from './media'

let indexPromise = null
let indexAt = 0
const INDEX_TTL_MS = 5 * 60 * 1000 // a page opened before the tables were published picks them up
const tables = new Map() // stem -> Promise<number[] | null>

async function tableBase() {
  return `${(await fetchMediaConfig()).image_base_url}/1/fps/frame_ms`
}

/** The set of videos that have a real-time table. A 404 means none (empty set);
 *  a network failure REJECTS, so a submission is refused rather than falling
 *  back to frame / fps on a video where that is wrong. */
export function timingIndex() {
  if (!indexPromise || Date.now() - indexAt > INDEX_TTL_MS) {
    indexAt = Date.now()
    indexPromise = tableBase()
      .then((base) => fetch(`${base}/index.json`, { cache: 'no-cache' }))
      .then((res) => {
        if (res.status === 404) return { videos: [] }
        if (!res.ok) throw new Error(`frame timing index: HTTP ${res.status}`)
        return res.json()
      })
      .then((json) => new Set(json.videos || []))
    indexPromise.catch(() => {
      indexPromise = null // retry on the next call
    })
  }
  return indexPromise
}

/** The video's real per-frame times (ms), or null when frame / fps is exact. */
export async function frameTable(videoName) {
  const stem = videoStem(videoName)
  if (!(await timingIndex()).has(stem)) return null
  if (!tables.has(stem)) {
    const promise = tableBase()
      .then((base) => fetch(`${base}/${stem}.json`))
      .then((res) => {
        if (!res.ok) throw new Error(`frame timing for ${stem}: HTTP ${res.status}`)
        return res.json()
      })
      .then((json) => json.ms)
    promise.catch(() => tables.delete(stem))
    tables.set(stem, promise)
  }
  return tables.get(stem)
}

/** Frame <-> seconds for one video: its real per-frame times when it has a table
 *  (`ms`), else frame / fps.
 *    msOf(f)     the frame's time, ms (what DRES is sent)
 *    startOf(f)  when the frame starts showing, s (timeline markers)
 *    timeOf(f)   a moment inside its display interval, s (seek there to show it)
 *    frameAt(t)  the frame showing at t seconds */
export function makeTimebase(ms, fps) {
  const rate = Number(fps)
  if (!Array.isArray(ms) || ms.length === 0) {
    return {
      table: false,
      msOf: (f) => Math.round((f / rate) * 1000),
      startOf: (f) => f / rate,
      timeOf: (f) => (f + 0.5) / rate,
      frameAt: (t) => Math.max(0, Math.floor(t * rate + 1e-3)),
    }
  }
  const last = ms.length - 1
  const step = last > 0 ? ms[last] - ms[last - 1] : 1000 / rate
  // never negative (OpenCV put frame 0 at its decode time, e.g. -200 ms)
  const msOf = (f) => Math.max(0, f <= last ? ms[Math.max(0, f)] : Math.round(ms[last] + (f - last) * step))
  return {
    table: true,
    msOf,
    startOf: (f) => msOf(f) / 1000,
    // just past the frame's start: the file holds frames OpenCV skipped, so the
    // midpoint to the next numbered frame can land on one of those instead
    timeOf: (f) => (msOf(f) + Math.min(5, (msOf(f + 1) - msOf(f)) / 2)) / 1000,
    frameAt: (t) => {
      const x = t * 1000 + 0.5
      if (x < ms[0]) return 0
      let lo = 0
      let hi = last
      while (lo < hi) {
        const mid = (lo + hi + 1) >> 1
        if (ms[mid] <= x) lo = mid
        else hi = mid - 1
      }
      return lo
    },
  }
}

/** A frame's time in the original video in ms (the DRES answer), or null when it
 *  cannot be known (bad frame number, no fps and no table). Rejects when the
 *  timing data cannot be loaded. */
export async function frameMs(videoName, frameId, fps) {
  const f = Number.parseInt(frameId, 10)
  if (!Number.isInteger(f) || f < 0) return null
  const ms = await frameTable(videoName)
  if (ms) return makeTimebase(ms, fps).msOf(f)
  const rate = Number(fps)
  if (!Number.isFinite(rate) || rate <= 0) return null
  return Math.round((f / rate) * 1000)
}
