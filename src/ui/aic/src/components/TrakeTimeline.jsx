import { useEffect, useRef, useState } from 'react'
import WaveSurfer from 'wavesurfer.js'
import RegionsPlugin from 'wavesurfer.js/dist/plugins/regions.esm.js'
import TimelinePlugin from 'wavesurfer.js/dist/plugins/timeline.esm.js'
import HoverPlugin from 'wavesurfer.js/dist/plugins/hover.esm.js'
import ZoomPlugin from 'wavesurfer.js/dist/plugins/zoom.esm.js'
import { formatTimecode } from '../api/media'


/**
 * TRAKE events as draggable markers on the video's own timeline.
 *
 * wavesurfer.js is used as a pure timeline: it attaches to the existing <video>
 * (`media`) with flat pre-supplied `peaks` + the `duration`, so it never fetches
 * or decodes the file (with no `url` it takes the video's own src, unchanged).
 * A Regions marker (a region with no end) = one event; drag it to move the event
 * (snapped to a frame), click it to seek there, double-click to remove it.
 * Markers are numbered in timeline order, which is the TRAKE event order.
 */
// `tb`: the video's frame <-> time mapping (api/timing.js makeTimebase)
export default function TrakeTimeline({ media, tb, marks, onChange, selected, onSelect }) {
  const containerRef = useRef(null)
  const wsRef = useRef(null)
  const regionsRef = useRef(null)
  const [ready, setReady] = useState(false)
  const [zoom, setZoom] = useState(0)
  // wavesurfer's handlers are bound once; read the latest props through refs
  const marksRef = useRef(marks)
  const onChangeRef = useRef(onChange)
  const onSelectRef = useRef(onSelect)
  useEffect(() => {
    marksRef.current = marks
    onChangeRef.current = onChange
    onSelectRef.current = onSelect
  })

  useEffect(() => {
    if (!media || !containerRef.current) return
    let ws = null
    let cancelled = false
    const frameOfRegion = (region) => Number(String(region.id).slice(1))

    const init = () => {
      if (cancelled || ws) return
      const duration = media.duration
      if (!Number.isFinite(duration) || duration <= 0) return
      const regions = RegionsPlugin.create()
      ws = WaveSurfer.create({
        container: containerRef.current,
        media,
        peaks: [[0, 0]],
        duration,
        height: 44,
        waveColor: 'rgba(0,0,0,0)',
        progressColor: 'rgba(99,102,241,0.15)',
        cursorColor: '#ef4444',
        cursorWidth: 2,
        dragToSeek: true,
        autoScroll: true,
        minPxPerSec: 0,
        plugins: [
          regions,
          TimelinePlugin.create({ height: 16, style: { fontSize: '10px', color: '#64748b' } }),
          HoverPlugin.create({
            lineColor: '#94a3b8',
            labelSize: '10px',
            formatTimeCallback: (s) => `${formatTimecode(s)} · frame ${tb.frameAt(s)}`,
          }),
          ZoomPlugin.create({ scale: 0.3, maxZoom: 400 }),
        ],
      })
      regions.on('region-updated', (region) => {
        const from = frameOfRegion(region)
        const to = Math.max(0, tb.frameAt(region.start))
        const next = marksRef.current.filter((f) => f !== from)
        if (!next.includes(to)) next.push(to)
        onChangeRef.current(next.sort((a, b) => a - b))
        onSelectRef.current?.(to)
        media.currentTime = tb.timeOf(to)
      })
      regions.on('region-clicked', (region, e) => {
        e.stopPropagation()
        const f = frameOfRegion(region)
        media.currentTime = tb.timeOf(f)
        onSelectRef.current?.(f)
      })
      regions.on('region-double-clicked', (region, e) => {
        e.stopPropagation()
        const f = frameOfRegion(region)
        onChangeRef.current(marksRef.current.filter((x) => x !== f))
        onSelectRef.current?.(null)
      })
      ws.on('zoom', (px) => setZoom(Math.round(px)))
      wsRef.current = ws
      regionsRef.current = regions
      setReady(true)
    }

    if (media.readyState >= 1) init()
    else media.addEventListener('loadedmetadata', init)
    return () => {
      cancelled = true
      media.removeEventListener('loadedmetadata', init)
      regionsRef.current = null
      wsRef.current = null
      setReady(false)
      ws?.destroy()
    }
  }, [media, tb])

  // (Re)draw the markers from `marks`: numbered in timeline order.
  useEffect(() => {
    const regions = regionsRef.current
    if (!ready || !regions) return
    regions.clearRegions()
    ;[...marks].sort((a, b) => a - b).forEach((f, i) => {
      const isSel = f === selected
      const tag = document.createElement('span')
      tag.textContent = String(i + 1)
      tag.title = `Event ${i + 1}, frame ${f}: drag to move · click = go to it · double-click = remove`
      tag.style.cssText =
        `display:inline-block;margin-left:-8px;min-width:16px;padding:0 3px;border-radius:8px;` +
        `font:600 10px/16px system-ui;text-align:center;color:#fff;cursor:grab;` +
        `background:${isSel ? '#ef4444' : '#4f46e5'}`
      regions.addRegion({ id: `f${f}`, start: tb.startOf(f), color: isSel ? '#ef4444' : '#4f46e5', drag: true, content: tag })
    })
  }, [marks, selected, tb, ready])

  return (
    <div className="w-full">
      <div ref={containerRef} className="w-full rounded bg-base-200" />
      <div className="flex items-center gap-2 mt-1 text-xs text-base-content/60">
        <span>zoom</span>
        <input
          type="range"
          min={0}
          max={400}
          step={5}
          value={zoom}
          className="range range-xs w-40"
          onChange={(e) => {
            const px = Number(e.target.value)
            setZoom(px)
            wsRef.current?.zoom(px)
          }}
        />
        <button type="button" className="btn btn-ghost btn-xs" onClick={() => { setZoom(0); wsRef.current?.zoom(0) }}>
          fit
        </button>
        <span className="ml-auto">drag a marker to move it · click = go to it · double-click = remove</span>
      </div>
    </div>
  )
}
