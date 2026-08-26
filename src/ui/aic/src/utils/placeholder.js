export const COLORS = ['#6366f1', '#ec4899', '#22c55e', '#f97316', '#06b6d4', '#a855f7', '#ef4444', '#0ea5e9']

export function placeholderThumbnail(label, color) {
  const svg = `<svg xmlns='http://www.w3.org/2000/svg' width='320' height='180'>
    <rect width='100%' height='100%' fill='${color}'/>
    <text x='50%' y='50%' font-size='28' fill='white' text-anchor='middle' dominant-baseline='middle' font-family='sans-serif'>${label}</text>
  </svg>`
  return `data:image/svg+xml;utf8,${encodeURIComponent(svg)}`
}
