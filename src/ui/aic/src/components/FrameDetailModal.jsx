import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { getNeighboringFrames } from '../api/search'
import { buildFrameUrl, buildVideoUrl, formatTimecode, videoStem } from '../api/media'
import { frameTable, makeTimebase } from '../api/timing'
import { useSubmissionStore } from '../stores/submissionStore'
import { useResultStore } from '../resultManager/store'
import { useSettingsStore } from '../stores/settingsStore'
import { Keyboard } from 'lucide-react'
import TrakeTimeline from './TrakeTimeline'
import { isEnter } from '../utils/keys'

// The frame viewer. Opens PAUSED on the clicked frame (no autoplay) and carries the
// submission actions itself, each acting on the frame showing now:
//   KIS    submit this frame's time
//   Q&A    type the answer, submit it for this frame
//   TRAKE  mark events on the timeline under the video (drag markers to adjust)
//
// `urls` overrides the media-config URLs (the result manager's CSV rows have no
// batch). `markMode`:
//   'dres' - the three DRES actions above; TRAKE marks are this viewer's own
//   'csv'  - the result manager: the timeline edits its marks (-> a CSV TRAKE row)
// `initialTab` / `initialMarks`: which panel opens first, and pre-marked TRAKE
// events (a temporal chain's "Use as TRAKE"). A card's TR opens TRAKE, empty.
// Shown as the keyboard icon's tooltip; each control also names its own key.
const SHORTCUTS = [
  'Keyboard shortcuts (click the viewer first, not a text box):',
  'Space  play / pause',
  '← / →  back / forward 1 second',
  ', / .  back / forward 1 frame',
  'M  mark a TRAKE event at the frame showing now',
  '[ / ]  go to the previous / next event',
  'Del  remove the selected event',
  'Esc  close the viewer',
].join('\n')

const VERDICT = {
  correct: 'alert-success',
  wrong: 'alert-error',
  error: 'alert-warning',
  info: 'alert-info',
}

const TABS = [
  ['kis', 'KIS'],
  ['qa', 'Q&A'],
  ['trake', 'TRAKE'],
]

export default function FrameDetailModal({
  record,
  mediaConfig,
  urls,
  markMode = 'dres',
  initialTab = 'kis',
  initialMarks = [],
  onClose,
}) {
  const isDres = markMode === 'dres'
  const dialogRef = useRef(null)
  const currentNeighborRef = useRef(null)
  // the <video>: a ref for reading/seeking, a state copy so the timeline re-renders
  const videoRef = useRef(null)
  const [videoEl, setVideoEl] = useState(null)
  const attachVideo = useCallback((el) => {
    videoRef.current = el
    setVideoEl(el)
  }, [])
  const [currentFrame, setCurrentFrame] = useState(null)
  const [tab, setTab] = useState(isDres ? initialTab : 'trake')
  const [qaAnswer, setQaAnswer] = useState('')
  // a temporal chain can repeat a frame: one event per frame, in timeline order
  const [ownMarks, setOwnMarks] = useState(() =>
    [...new Set(initialMarks.map(Number).filter((f) => Number.isInteger(f) && f >= 0))].sort((a, b) => a - b),
  )
  const [selectedMark, setSelectedMark] = useState(null)
  const [goTo, setGoTo] = useState('')
  const neighborCount = useSettingsStore((s) => s.neighborFrameCount)
  const busy = useSubmissionStore((s) => s.busy)
  const submitFrameKis = useSubmissionStore((s) => s.submitFrameKis)
  const submitQaAnswer = useSubmissionStore((s) => s.submitQaAnswer)
  const submitTrakeFrames = useSubmissionStore((s) => s.submitTrakeFrames)
  // the last submit's verdict: the global toast sits under this modal's backdrop
  const last = useSubmissionStore((s) => s.last)
  const clearLast = useSubmissionStore((s) => s.clearLast)
  const csvMarks = useResultStore((s) => s.marks)
  const csvMarkVideo = useResultStore((s) => s.markVideo)
  const updateResultStore = useResultStore((s) => s.update)

  const videoName = record ? videoStem(record.video_name) : null
  // Do NOT silently fall back to 25: fps varies across the dataset, so a guessed
  // fps produces a time that looks right and is not. Actions are disabled instead.
  const rawFps = Number(record?.fps)
  const fpsKnown = Number.isFinite(rawFps) && rawFps > 0
  const fps = fpsKnown ? rawFps : 25
  // Frame <-> time (api/timing.js): the real per-frame times on the irregular
  // traffic cams, frame / fps elsewhere. The player is not shown until this is
  // known, so it never opens (and marks) on the frame / fps guess.
  const timing = useQuery({
    queryKey: ['frameTable', record ? videoStem(record.video_name) : null],
    queryFn: () => frameTable(record.video_name),
    enabled: Boolean(record),
    staleTime: 60 * 1000, // the timing index is re-read every 5 min (api/timing.js)
    retry: 2,
  })
  const timingReady = timing.isSuccess
  const tb = useMemo(() => makeTimebase(timing.data, fps), [timing.data, fps])
  const startFrame = record ? Number(record.keyframe_id) : 0
  const startSeconds = record && timingReady ? tb.timeOf(startFrame) : null
  const videoUrl = urls?.video ?? buildVideoUrl(mediaConfig, record)
  const frameUrl = urls?.frame ?? buildFrameUrl(mediaConfig, record)

  // TRAKE marks: this viewer's own (DRES), or the result manager's for this video (CSV)
  const marks = useMemo(
    () => (isDres ? ownMarks : csvMarkVideo === videoName ? csvMarks.map(Number) : []),
    [isDres, ownMarks, csvMarkVideo, videoName, csvMarks],
  )
  const setMarks = useCallback(
    (frames) => {
      const sorted = [...new Set(frames.map(Number))].sort((a, b) => a - b)
      if (isDres) return setOwnMarks(sorted)
      // the result store keeps ONE video's marks: marking another video drops them
      if (
        csvMarkVideo && csvMarkVideo !== videoName && csvMarks.length &&
        !window.confirm(`${csvMarks.length} frame(s) are marked on ${csvMarkVideo}.\nMark ${videoName} instead? (the ${csvMarkVideo} marks are dropped)`)
      )
        return
      updateResultStore({ marks: sorted, markVideo: videoName })
    },
    [isDres, updateResultStore, videoName, csvMarkVideo, csvMarks],
  )

  // The util service may not be running; a failure here must not break the modal.
  const { data: neighbors } = useQuery({
    queryKey: ['neighbors', videoName, record?.keyframe_id, neighborCount],
    queryFn: () => getNeighboringFrames(videoName, record.keyframe_id, neighborCount),
    enabled: Boolean(record && videoName && !urls),
    retry: false,
  })

  useEffect(() => {
    const dialog = dialogRef.current
    if (!dialog) return
    if (record) dialog.showModal()
    else if (dialog.open) dialog.close()
    setCurrentFrame(record ? startFrame : null)
  }, [record, startFrame])

  // Paused on the clicked frame; track the frame showing as it plays / is scrubbed.
  useEffect(() => {
    const el = videoRef.current
    if (!el || startSeconds == null) return
    const seek = () => {
      el.currentTime = startSeconds
    }
    const track = () => setCurrentFrame(tb.frameAt(el.currentTime))
    if (el.readyState >= 1) seek()
    el.addEventListener('loadedmetadata', seek)
    el.addEventListener('timeupdate', track)
    el.addEventListener('seeked', track)
    return () => {
      el.removeEventListener('loadedmetadata', seek)
      el.removeEventListener('timeupdate', track)
      el.removeEventListener('seeked', track)
    }
  }, [videoEl, startSeconds, tb])

  const frameNow = currentFrame ?? startFrame
  // The player's position. Until its metadata has loaded (slow link) currentTime
  // is 0, not the opened frame: marking / stepping / submitting from it would use
  // frame 0. Use the frame the viewer shows instead.
  const playerSeconds = useCallback(
    () => (videoRef.current?.readyState >= 1 ? videoRef.current.currentTime : tb.timeOf(frameNow)),
    [frameNow, tb],
  )

  const seekTo = useCallback(
    (seconds) => {
      const el = videoRef.current
      if (!el) return
      const target = Math.max(0, Math.min(el.duration || Infinity, seconds))
      el.currentTime = target
      setCurrentFrame(tb.frameAt(target))
    },
    [tb],
  )
  const nudge = useCallback((deltaSeconds) => seekTo(playerSeconds() + deltaSeconds), [seekTo, playerSeconds])
  const stepFrames = useCallback(
    (n) => seekTo(tb.timeOf(tb.frameAt(playerSeconds()) + n)),
    [tb, seekTo, playerSeconds],
  )

  const frameRecord = record && {
    video_name: record.video_name,
    keyframe_id: currentFrame ?? startFrame,
    // the real fps (null if unknown), never the display fallback
    fps: fpsKnown ? fps : null,
  }

  const markCurrentFrame = useCallback(() => {
    if (!record || !fpsKnown || !timingReady) return
    const f = tb.frameAt(playerSeconds())
    setMarks([...marks, f])
    setSelectedMark(f)
    setTab('trake')
  }, [record, fpsKnown, timingReady, tb, playerSeconds, marks, setMarks])

  const removeMark = useCallback(
    (f) => {
      setMarks(marks.filter((x) => x !== f))
      if (selectedMark === f) setSelectedMark(null)
    },
    [marks, selectedMark, setMarks],
  )

  const jumpMark = useCallback(
    (dir) => {
      if (!marks.length) return
      const sorted = [...marks].sort((a, b) => a - b)
      const here = tb.frameAt(playerSeconds())
      const target =
        dir > 0 ? sorted.find((f) => f > here) ?? sorted[0] : [...sorted].reverse().find((f) => f < here) ?? sorted.at(-1)
      setSelectedMark(target)
      seekTo(tb.timeOf(target))
    },
    [marks, tb, seekTo, playerSeconds],
  )

  // "go to": a frame number, or mm:ss / hh:mm:ss
  const doGoTo = () => {
    const v = goTo.trim()
    if (!v) return
    if (v.includes(':')) {
      const secs = v.split(':').reduce((acc, p) => acc * 60 + Number(p), 0)
      if (Number.isFinite(secs)) seekTo(secs)
    } else if (Number.isFinite(Number(v))) seekTo(tb.timeOf(Number(v)))
    setGoTo('')
  }

  // Legacy keys, scoped to the (modal) dialog; typing in a field is left alone.
  useEffect(() => {
    const dialog = dialogRef.current
    if (!dialog || !record) return
    const onKeyDown = (e) => {
      const t = e.target
      if (t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA')) return
      const k = e.key
      if (k === ' ') {
        e.preventDefault()
        const v = videoRef.current
        if (v) v.paused ? v.play() : v.pause()
      } else if (k === 'ArrowLeft') {
        e.preventDefault()
        nudge(-1)
      } else if (k === 'ArrowRight') {
        e.preventDefault()
        nudge(1)
      } else if (k === ',') {
        e.preventDefault()
        stepFrames(-1)
      } else if (k === '.') {
        e.preventDefault()
        stepFrames(1)
      } else if (k.toLowerCase() === 'm') {
        e.preventDefault()
        markCurrentFrame()
      } else if ((k === 'Delete' || k === 'Backspace') && selectedMark != null) {
        e.preventDefault()
        removeMark(selectedMark)
      } else if (k === '[') {
        e.preventDefault()
        jumpMark(-1)
      } else if (k === ']') {
        e.preventDefault()
        jumpMark(1)
      }
    }
    dialog.addEventListener('keydown', onKeyDown)
    return () => dialog.removeEventListener('keydown', onKeyDown)
  }, [record, nudge, stepFrames, markCurrentFrame, removeMark, selectedMark, jumpMark])

  const transcript = Array.isArray(record?.s2t) ? record.s2t.join(' ') : ''
  const sortedMarks = useMemo(() => [...marks].sort((a, b) => a - b), [marks])
  // the same time the submission carries (the store asks api/timing.js too)
  const ms = frameRecord && fpsKnown && timingReady ? tb.msOf(Number(frameRecord.keyframe_id)) : null

  // The clicked frame sits between its neighbours, so the strip reads as a timeline.
  const neighborStrip = useMemo(() => {
    const prev = neighbors?.prev_frames || []
    const next = neighbors?.next_frames || []
    return [
      ...prev.map((path) => ({ path, current: false })),
      { path: frameUrl, current: true },
      ...next.map((path) => ({ path, current: false })),
    ]
  }, [neighbors, frameUrl])

  const centreCurrentNeighbor = useCallback((smooth = true) => {
    const el = currentNeighborRef.current
    const strip = el?.parentElement
    if (!el || !strip) return
    strip.scrollTo({
      left: el.offsetLeft - (strip.clientWidth - el.clientWidth) / 2,
      behavior: smooth ? 'smooth' : 'auto',
    })
  }, [])
  useEffect(() => {
    if (neighborStrip.length <= 1) return
    centreCurrentNeighbor(false)
  }, [neighborStrip, centreCurrentNeighbor])

  const noFps = "Unavailable: this video's fps is unknown, so the frame time cannot be computed"

  return (
    <dialog ref={dialogRef} className="modal" onClose={onClose}>
      {record && (
        <div className="modal-box max-w-4xl">
          <div className="flex items-baseline justify-between gap-2">
            <h3 className="font-semibold text-lg">{videoName}</h3>
            <span className="text-sm text-base-content/60">
              opened at frame {startFrame} · {fpsKnown ? `${fps} fps` : 'fps unknown'}
              {record.score > 0 && <> · score {record.score.toFixed(4)}</>} · shot {record.related_start_frame}–
              {record.related_end_frame}
            </span>
          </div>

          {videoUrl && timingReady ? (
            <video
              ref={attachVideo}
              src={`${videoUrl}#t=${startSeconds}`}
              poster={frameUrl || undefined}
              controls
              preload="metadata"
              title="Space = play / pause · ← → = ±1 s · , . = ±1 frame · M = mark event"
              className="w-full rounded-lg aspect-video bg-black mt-2"
            />
          ) : (
            <div className="relative mt-2">
              <img src={frameUrl} alt={videoName} className="w-full rounded-lg aspect-video object-contain bg-black" />
              {videoUrl && !timingReady && (
                <span className={`badge absolute top-2 left-2 ${timing.isError ? 'badge-warning' : 'badge-ghost'}`}>
                  {timing.isError
                    ? "Could not load this video's frame timing: player and submit are off. Reopen to retry."
                    : 'loading…'}
                </span>
              )}
            </div>
          )}

          <div className="flex items-center justify-center gap-3 mt-2 text-sm flex-wrap">
            <span>
              <strong>Frame:</strong> {currentFrame ?? '—'}{' '}
              <span className="text-base-content/50">{formatTimecode(tb.startOf(currentFrame ?? 0))}</span>
            </span>
            <div className="join">
              <button type="button" className="btn btn-xs join-item" onClick={() => nudge(-1)} title="Back 1 second (←)">« 1s</button>
              <button type="button" className="btn btn-xs join-item" onClick={() => stepFrames(-1)} title="Back 1 frame (,)">‹ 1f</button>
              <button type="button" className="btn btn-xs join-item" onClick={() => stepFrames(1)} title="Forward 1 frame (.)">1f ›</button>
              <button type="button" className="btn btn-xs join-item" onClick={() => nudge(1)} title="Forward 1 second (→)">1s »</button>
            </div>
            <input
              className="input input-xs input-bordered w-36"
              placeholder="go to frame / mm:ss"
              title="Type a frame number or mm:ss, then Enter"
              value={goTo}
              onChange={(e) => setGoTo(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && doGoTo()}
            />
            {frameUrl && (
              <a href={frameUrl} target="_blank" rel="noreferrer" className="btn btn-xs btn-ghost">Open frame</a>
            )}
            <span className="text-base-content/50 cursor-help" title={SHORTCUTS} aria-label="Keyboard shortcuts">
              <Keyboard size={16} />
            </span>
          </div>

          {videoUrl && fpsKnown && (
            <div className="mt-2">
              <TrakeTimeline
                media={videoEl}
                tb={tb}
                marks={marks}
                onChange={setMarks}
                selected={selectedMark}
                onSelect={setSelectedMark}
              />
            </div>
          )}

          {/* ---- submit (DRES) / marks (CSV) ---- */}
          <div className="mt-3 border border-base-300 rounded-lg p-3">
            {isDres && (
              <div role="tablist" className="tabs tabs-boxed tabs-sm mb-3">
                {TABS.map(([t, label]) => (
                  <button
                    key={t}
                    type="button"
                    role="tab"
                    className={`tab ${tab === t ? 'tab-active' : ''}`}
                    onClick={() => setTab(t)}
                  >
                    {label}
                    {t === 'trake' && marks.length > 0 && ` (${marks.length})`}
                  </button>
                ))}
              </div>
            )}

            {isDres && tab === 'kis' && (
              <div className="flex items-center gap-3 flex-wrap">
                <span className="text-sm">
                  Submit the frame showing now: <strong>{videoName}</strong> · frame {frameRecord.keyframe_id}
                  {ms != null && <> · {ms} ms</>}
                </span>
                <button
                  type="button"
                  className="btn btn-sm btn-primary ml-auto"
                  disabled={busy || !fpsKnown || !timingReady}
                  title={fpsKnown ? 'Submit this frame to DRES as KIS' : noFps}
                  onClick={() => submitFrameKis(frameRecord)}
                >
                  Submit KIS
                </button>
              </div>
            )}

            {isDres && tab === 'qa' && (
              <div className="flex items-center gap-2 flex-wrap">
                <input
                  className="input input-sm input-bordered flex-1 min-w-48"
                  placeholder="Answer…"
                  title="Enter submits"
                  value={qaAnswer}
                  onChange={(e) => setQaAnswer(e.target.value)}
                  onKeyDown={(e) => {
                    if (isEnter(e)) submitQaAnswer(frameRecord, qaAnswer)
                  }}
                />
                <span className="text-xs text-base-content/60">
                  for frame {frameRecord.keyframe_id}
                  {ms != null && <> ({ms} ms)</>}
                </span>
                <button
                  type="button"
                  className="btn btn-sm btn-primary"
                  disabled={busy || !fpsKnown || !timingReady || !qaAnswer.trim()}
                  title={fpsKnown ? 'Submit this answer for the frame showing now (Enter in the answer box)' : noFps}
                  onClick={() => submitQaAnswer(frameRecord, qaAnswer)}
                >
                  Submit Q&amp;A
                </button>
              </div>
            )}

            {tab === 'trake' && (
              <div>
                <div className="flex items-center gap-2 flex-wrap">
                  <button
                    type="button"
                    className="btn btn-sm btn-outline"
                    onClick={markCurrentFrame}
                    disabled={!fpsKnown || !timingReady}
                    title={fpsKnown ? 'Add an event at the frame showing now (M)' : noFps}
                  >
                    Mark frame {frameNow} (M)
                  </button>
                  <span className="text-xs text-base-content/60">
                    {sortedMarks.length} event{sortedMarks.length === 1 ? '' : 's'} · [ ] = previous / next event · Del = remove
                  </span>
                  <div className="ml-auto flex gap-2">
                    <button type="button" className="btn btn-sm btn-ghost" disabled={!marks.length} onClick={() => setMarks([])} title="Remove all events">
                      Clear
                    </button>
                    {isDres && (
                      <button
                        type="button"
                        className="btn btn-sm btn-primary"
                        disabled={busy || !marks.length}
                        title="Submit these events, in timeline order, as one TRAKE answer"
                        onClick={() => submitTrakeFrames(record.video_name, sortedMarks)}
                      >
                        Submit TRAKE
                      </button>
                    )}
                  </div>
                </div>
                {sortedMarks.length > 0 && (
                  <ol className="flex flex-wrap gap-2 mt-2">
                    {sortedMarks.map((f, i) => (
                      <li
                        key={f}
                        className={`badge badge-lg gap-2 cursor-pointer ${f === selectedMark ? 'badge-error text-white' : ''}`}
                        title="Go to this event and select it ([ / ] = previous / next, Del = remove)"
                        onClick={() => {
                          setSelectedMark(f)
                          seekTo(tb.timeOf(f))
                        }}
                      >
                        <span className="font-semibold">{i + 1}</span> {f}
                        <span className="text-xs opacity-60">{formatTimecode(tb.startOf(f))}</span>
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation()
                            removeMark(f)
                          }}
                          aria-label={`Remove event at frame ${f}`}
                          title="Remove this event (or select it and press Del)"
                        >
                          ✕
                        </button>
                      </li>
                    ))}
                  </ol>
                )}
                {!isDres && (
                  <p className="text-xs text-base-content/50 mt-2">
                    Marks become one TRAKE row via &quot;Add as TRAKE row&quot; in the Marked frames panel.
                  </p>
                )}
              </div>
            )}
          </div>

          {isDres && last && (
            <div role="status" className={`alert ${VERDICT[last.kind] || 'alert-info'} py-1 px-3 text-xs gap-2 mt-2`}>
              <span className="truncate">{last.text}</span>
              <button type="button" className="btn btn-xs btn-ghost" onClick={clearLast} aria-label="Dismiss">
                ✕
              </button>
            </div>
          )}

          {transcript && (
            <div className="mt-4">
              <h4 className="font-semibold text-sm mb-1">Transcript</h4>
              <p className="text-xs text-base-content/70 max-h-24 overflow-y-auto">{transcript}</p>
            </div>
          )}

          {neighborStrip.length > 1 && (
            <div className="mt-4">
              <h4 className="font-semibold text-sm mb-2">Neighbouring frames</h4>
              <div className="flex gap-2 overflow-x-auto pb-2 scroll-smooth">
                {neighborStrip.map((item, i) => (
                  <img
                    key={`${item.path}:${i}`}
                    ref={item.current ? currentNeighborRef : undefined}
                    src={item.current ? item.path : `${mediaConfig?.image_base_url}/${item.path}`}
                    alt={item.current ? 'current frame' : item.path}
                    loading="lazy"
                    title={item.current ? 'Current frame' : undefined}
                    onLoad={item.current ? () => centreCurrentNeighbor(false) : undefined}
                    className={`h-20 w-36 object-cover rounded shrink-0 ${
                      item.current ? 'border-2 border-primary ring-2 ring-primary/40' : 'border border-base-300 opacity-70'
                    }`}
                  />
                ))}
              </div>
            </div>
          )}

          <div className="modal-action">
            <form method="dialog">
              <button className="btn" title="Close (Esc)">Close</button>
            </form>
          </div>
        </div>
      )}
      <form method="dialog" className="modal-backdrop">
        <button>close</button>
      </form>
    </dialog>
  )
}
