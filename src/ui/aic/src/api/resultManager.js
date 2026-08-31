// Result-manager service. It resolves a video's batch server-side, which the
// review flow needs: a CSV row carries only video_id,keyframe_id -- no batch --
// so the browser cannot build a media URL itself.
import { get } from './client'

// Same-origin by default; /result_manager is proxied by the dev server.
export const RESULT_MANAGER_BASE_URL = (
  import.meta.env.VITE_RESULT_MANAGER_BASE_URL || ''
).replace(/\/+$/, '')

function stem(videoId) {
  return String(videoId ?? '').split('.')[0]
}

/** Thumbnail URL for a CSV row; the service redirects to the media server. */
export function resultFrameUrl(videoId, keyframeId, { original = false } = {}) {
  if (!videoId || keyframeId == null || keyframeId === '') return null
  const route = original ? 'send_img_original' : 'send_img'
  const frame = String(keyframeId).split('.')[0]
  return `${RESULT_MANAGER_BASE_URL}/result_manager/${route}/${stem(videoId)}/${frame}`
}

export function resultVideoUrl(videoId) {
  if (!videoId) return null
  return `${RESULT_MANAGER_BASE_URL}/result_manager/send_video/${stem(videoId)}`
}

/** Frame rate, so the reviewer can seek the video to a CSV row's frame. */
export async function getFps(videoId) {
  const data = await get(`/result_manager/get_fps/${stem(videoId)}`, RESULT_MANAGER_BASE_URL)
  return Number(data) || null
}
