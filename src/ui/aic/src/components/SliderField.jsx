import { useState } from 'react'

function clamp(value, min, max) {
  if (Number.isNaN(value)) return min
  return Math.min(max, Math.max(min, value))
}

export default function SliderField({ label, min, max, step = 1, value, onChange }) {
  // The box keeps what is typed and clamps on blur / Enter: clamping every
  // keystroke turned "300" into 1000 ("3" -> 10, then "100", "1000").
  const [draft, setDraft] = useState(null)
  const commit = () => {
    if (draft != null) onChange(clamp(Number(draft), min, max))
    setDraft(null)
  }
  return (
    <div>
      <div className="flex items-center justify-between mb-1 gap-2">
        <span className="text-xs uppercase tracking-wide text-base-content/60">{label}</span>
        <input
          type="number"
          min={min}
          max={max}
          step={step}
          value={draft ?? value}
          onChange={(e) => setDraft(e.target.value)}
          onBlur={commit}
          onKeyDown={(e) => e.key === 'Enter' && commit()}
          className="input input-bordered input-xs w-16 text-right font-mono"
        />
      </div>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="range range-xs"
      />
    </div>
  )
}
