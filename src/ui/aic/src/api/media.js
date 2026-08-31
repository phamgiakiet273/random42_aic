// Media URLs come from the layout rule the hub publishes at
// GET /hub/media_config, not a hardcoded copy. Records carry only
// `idx_folder`, `video_name` and `keyframe_id` (doc comment [p]).
import { get } from './client'

let configPromise = null

// The hub publishes absolute bases (http://localhost:9027/img), which only work
// when the browser runs on the server. Keep just the path so requests stay
// same-origin and the dev-server proxy forwards them.
function toSameOrigin(baseUrl, override) {
  if (override) return override.replace(/\/+$/, '')
  if (!baseUrl) return ''
  try {
    return new URL(baseUrl).pathname.replace(/\/+$/, '')
  } catch {
    // Already a bare path such as "/img".
    return String(baseUrl).replace(/\/+$/, '')
  }
}

function normaliseConfig(config) {
  return {
    ...config,
    image_base_url: toSameOrigin(
      config.image_base_url,
      import.meta.env.VITE_MEDIA_BASE_URL,
    ),
    video_base_url: toSameOrigin(
      config.video_base_url,
      import.meta.env.VITE_MEDIA_BASE_URL,
    ),
  }
}

export function fetchMediaConfig() {
  if (!configPromise) {
    configPromise = get('/hub/media_config')
      .then(normaliseConfig)
      .catch((err) => {
        // Let a later call retry rather than caching the failure forever.
        configPromise = null
        throw err
      })
  }
  return configPromise
}

export function videoStem(videoName) {
  return String(videoName ?? '').split('.')[0]
}

export function videoPrefix(videoName) {
  return videoStem(videoName).split('_')[0]
}

function render(template, values) {
  return template.replace(/\{(\w+)\}/g, (_, key) => values[key] ?? '')
}

export function buildFrameUrl(config, record, { original = false } = {}) {
  if (!config || !record) return null
  const { video_name: videoName, keyframe_id: keyframeId, idx_folder: batch } = record
  if (videoName == null || keyframeId == null) return null
  const path = render(config.frame_template, {
    batch: batch ?? 0,
    split: original ? config.split_original : config.split,
    prefix: videoPrefix(videoName),
    video: videoStem(videoName),
    keyframe: String(keyframeId).split('.')[0].padStart(config.keyframe_pad ?? 5, '0'),
    ext: config.frame_ext,
  })
  return `${config.image_base_url}/${path}`
}

export function buildVideoUrl(config, record) {
  if (!config || !record) return null
  const { video_name: videoName, idx_folder: batch } = record
  if (videoName == null) return null
  const path = render(config.video_template, {
    batch: batch ?? 0,
    prefix: videoPrefix(videoName),
    video: videoStem(videoName),
  })
  return `${config.video_base_url}/${path}`
}

// Frame index -> seconds, so the video element can seek to the frame the user
// clicked (doc comment [j]).
export function frameToSeconds(keyframeId, fps) {
  const frame = Number(keyframeId)
  const rate = Number(fps)
  if (!Number.isFinite(frame) || !Number.isFinite(rate) || rate <= 0) return null
  return frame / rate
}

export function formatTimecode(totalSeconds) {
  if (totalSeconds == null || !Number.isFinite(totalSeconds)) return '—'
  const h = String(Math.floor(totalSeconds / 3600)).padStart(2, '0')
  const m = String(Math.floor((totalSeconds % 3600) / 60)).padStart(2, '0')
  const s = String(Math.floor(totalSeconds % 60)).padStart(2, '0')
  return `${h}:${m}:${s}`
}
