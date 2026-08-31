function clamp(value, min, max) {
  if (Number.isNaN(value)) return min
  return Math.min(max, Math.max(min, value))
}

export default function SliderField({ label, min, max, step = 1, value, onChange }) {
  return (
    <div>
      <div className="flex items-center justify-between mb-1 gap-2">
        <span className="text-xs uppercase tracking-wide text-base-content/60">{label}</span>
        <input
          type="number"
          min={min}
          max={max}
          step={step}
          value={value}
          onChange={(e) => onChange(clamp(Number(e.target.value), min, max))}
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
