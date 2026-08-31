export const MEDIA_BASE_URL = import.meta.env.VITE_MEDIA_BASE_URL || ''

// Best-effort thumbnail URL for an arbitrary video_id/keyframe_id (e.g. from
// an uploaded CSV, where we don't have a real search-result record).
// `batch` is unresolvable per-video without backend/dataset-index data --
// 0 is the only batch confirmed working this session (verified against
// L21_V001), so it's used as a best guess. Callers should fall back to a
// placeholder image on load error, since this can 404 for videos that are
// actually in a different batch.
export function buildThumbnailUrl(videoId, keyframeId) {
  if (!MEDIA_BASE_URL || !videoId || keyframeId == null || keyframeId === '') return null
  const prefix = videoId.split('_')[0]
  const frame = `${String(keyframeId).padStart(5, '0')}.avif`
  return `${MEDIA_BASE_URL}/img/0/frames/autoshot/Keyframes_${prefix}/keyframes/${videoId}/${frame}`
}
