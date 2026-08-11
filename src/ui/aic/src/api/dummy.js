

const COLORS = ['#6366f1', '#ec4899', '#22c55e', '#f97316', '#06b6d4', '#a855f7', '#ef4444', '#0ea5e9']

function formatTimestamp(totalSeconds) {
  const m = String(Math.floor(totalSeconds / 60)).padStart(2, '0')
  const s = String(totalSeconds % 60).padStart(2, '0')
  return `00:${m}:${s}`
}

function placeholderThumbnail(label, color) {
  const svg = `<svg xmlns='http://www.w3.org/2000/svg' width='320' height='180'>
    <rect width='100%' height='100%' fill='${color}'/>
    <text x='50%' y='50%' font-size='28' fill='white' text-anchor='middle' dominant-baseline='middle' font-family='sans-serif'>${label}</text>
  </svg>`
  return `data:image/svg+xml;utf8,${encodeURIComponent(svg)}`
}

const records = COLORS.map((color, i) => {
  const index = i + 1
  return {
    id: index,
    video_id: `L01_V${String(index).padStart(3, '0')}`,
    title: `Sample keyframe ${index}`,
    timestamp: formatTimestamp(index * 37),
    thumbnail_url: placeholderThumbnail(`Frame ${index}`, color),
  }
})

export async function list() {
  return { status: 200, message: 'Success', data: records }
}
