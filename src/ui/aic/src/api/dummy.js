import { COLORS, placeholderThumbnail } from '../utils/placeholder'

const MEDIA_BASE_URL = import.meta.env.VITE_MEDIA_BASE_URL || ''

const REAL_FRAMES = [
  '00000.avif', '04429.avif', '09957.avif', '12866.avif', '17581.avif', '22485.avif', '27254.avif', '30408.avif', '34283.avif',
  '00026.avif', '04489.avif', '10048.avif', '12890.avif', '17827.avif', '22510.avif', '27307.avif', '30425.avif', '34319.avif',
  '00053.avif', '04550.avif', '10140.avif', '12914.avif', '18073.avif', '22535.avif', '27360.avif', '30442.avif', '34355.avif',
  '00054.avif', '04551.avif', '10141.avif', '12915.avif', '18074.avif', '22536.avif', '27361.avif', '30443.avif', '34356.avif',
  '00198.avif', '04618.avif', '10182.avif', '12938.avif', '18126.avif', '22548.avif', '27441.avif', '30483.avif', '34400.avif',
  '00342.avif', '04686.avif', '10224.avif', '12961.avif', '18179.avif', '22561.avif', '27522.avif', '30524.avif', '34444.avif',
  '00343.avif', '04687.avif', '10225.avif', '12962.avif', '18180.avif', '22562.avif', '27523.avif', '30525.avif', '34445.avif',
  '00376.avif', '04760.avif', '10271.avif', '12986.avif', '18212.avif', '22634.avif', '27624.avif', '30584.avif', '34489.avif',
  '00410.avif', '04834.avif', '10318.avif', '13010.avif', '18245.avif', '22706.avif', '27726.avif', '30644.avif', '34534.avif',
  '00411.avif', '04835.avif', '10319.avif',
]
const REAL_VIDEO = { batch: 0, prefix: 'L21', video: 'L21_V001' }
const REAL_FPS = 25

function realThumbnailUrl(index) {
  const frame = REAL_FRAMES[index % REAL_FRAMES.length]
  return `${MEDIA_BASE_URL}/img/${REAL_VIDEO.batch}/frames/autoshot/Keyframes_${REAL_VIDEO.prefix}/keyframes/${REAL_VIDEO.video}/${frame}`
}

function realVideoUrl() {
  return `${MEDIA_BASE_URL}/video/${REAL_VIDEO.batch}/videos/Videos_${REAL_VIDEO.prefix}/video/${REAL_VIDEO.video}.mp4`
}

function realKeyframeId(index) {
  const frame = REAL_FRAMES[index % REAL_FRAMES.length]
  return parseInt(frame, 10)
}

function realFrameName(index) {
  return REAL_FRAMES[index % REAL_FRAMES.length]
}

function formatTimestamp(totalSeconds) {
  const m = String(Math.floor(totalSeconds / 60)).padStart(2, '0')
  const s = String(totalSeconds % 60).padStart(2, '0')
  return `00:${m}:${s}`
}

const RECORD_COUNT = 100

const records = Array.from({ length: RECORD_COUNT }, (_, i) => {
  const index = i + 1
  const timestamp = formatTimestamp(index * 37)

  if (MEDIA_BASE_URL) {
    return {
      id: index,
      video_id: REAL_VIDEO.video,
      title: REAL_VIDEO.video,
      frame_name: realFrameName(i),
      timestamp,
      thumbnail_url: realThumbnailUrl(i),
      video_path: realVideoUrl(),
      keyframe_id: realKeyframeId(i),
      fps: REAL_FPS,
    }
  }

  return {
    id: index,
    video_id: `L01_V${String(index).padStart(3, '0')}`,
    title: 'Invalid Keyframe',
    timestamp,
    thumbnail_url: placeholderThumbnail(`Frame ${index}`, COLORS[i % COLORS.length]),
  }
})

export async function list() {
  return { status: 200, message: 'Success', data: records }
}

export async function listVideoNames() {
  const uniqueNames = [...new Set(records.map((record) => record.video_id))]
  return { status: 200, message: 'Success', data: uniqueNames }
}

export async function submitTrake(videoId, frameIds) {
  return { status: 200, message: 'Success', data: { submit_result: 'ok', video_id: videoId, frame_ids: frameIds } }
}
