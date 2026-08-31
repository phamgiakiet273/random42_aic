// Frame-class colours, matching the legacy UI so the mapping stays familiar
// (it drew them as a 3px border; here they tint the rank badge on each card).
// Translucent: the badge should read as an overlay on the frame, not compete
// with it. Colour still encodes frame_class, as legacy's border did.
const COLORS = {
  0: { badge: 'bg-red-500/30 text-white', label: 'class 0' },
  1: { badge: 'bg-orange-500/30 text-white', label: 'class 1' },
  2: { badge: 'bg-green-600/30 text-white', label: 'class 2' },
  3: { badge: 'bg-yellow-400/35 text-black', label: 'class 3' },
}

const UNKNOWN = { badge: 'bg-neutral/25 text-neutral-content', label: 'class unknown' }

export function frameClassStyle(frameClass) {
  if (frameClass == null) return UNKNOWN
  return COLORS[Number(frameClass)] ?? UNKNOWN
}
