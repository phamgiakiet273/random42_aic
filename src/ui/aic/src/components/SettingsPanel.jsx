import { useSettingsStore } from '../stores/settingsStore'
import SliderField from './SliderField'

const FRAME_CLASSES = [0, 1, 2, 3]

export default function SettingsPanel() {
  const settings = useSettingsStore()

  return (
    <div className="card bg-base-100 shadow-sm">
      <div className="card-body gap-4">
        <h2 className="card-title text-base">Settings</h2>

        <label className="label cursor-pointer justify-start gap-2">
        <input
          type="checkbox"
          className="checkbox checkbox-sm"
          checked={settings.returnS2t}
          onChange={(e) => settings.update({ returnS2t: e.target.checked })}
        />
        <span className="label-text">S2T Info</span>
      </label>

      <label className="label cursor-pointer justify-start gap-2">
        <input
          type="checkbox"
          className="checkbox checkbox-sm"
          checked={settings.returnObject}
          onChange={(e) => settings.update({ returnObject: e.target.checked })}
        />
        <span className="label-text">Objects Info</span>
      </label>

      <div>
        <p className="text-xs uppercase tracking-wide text-base-content/60 mb-1">Frame Class Filter</p>
        <div className="flex gap-3">
          {FRAME_CLASSES.map((value) => (
            <label key={value} className="label cursor-pointer gap-1">
              <input
                type="checkbox"
                className="checkbox checkbox-sm"
                checked={settings.frameClassFilter.includes(value)}
                onChange={() => settings.toggleFrameClass(value)}
              />
              <span className="label-text">{value}</span>
            </label>
          ))}
        </div>
      </div>

      <label className="label cursor-pointer justify-start gap-2">
        <input
          type="checkbox"
          className="checkbox checkbox-sm"
          checked={settings.autoTranslate}
          onChange={(e) => settings.update({ autoTranslate: e.target.checked })}
        />
        <span className="label-text">Auto Translate</span>
      </label>

      <label className="label cursor-pointer justify-start gap-2">
        <input
          type="checkbox"
          className="checkbox checkbox-sm"
          checked={settings.immediateRerun}
          onChange={(e) => settings.update({ immediateRerun: e.target.checked })}
        />
        <span className="label-text">Immediate Re-search on Skip</span>
      </label>

      <SliderField
        label="Number of Results"
        min={10}
        max={1000}
        step={10}
        value={settings.topK}
        onChange={(v) => settings.update({ topK: v })}
      />
      <SliderField
        label="Results per Page"
        min={10}
        max={200}
        step={10}
        value={settings.resultsPerPage}
        onChange={(v) => settings.update({ resultsPerPage: v })}
      />
      <SliderField
        label="Neighbor Frames Count"
        min={1}
        max={50}
        step={1}
        value={settings.neighborFrameCount}
        onChange={(v) => settings.update({ neighborFrameCount: v })}
      />
      <SliderField
        label="Thumbnail Size"
        min={100}
        max={400}
        step={10}
        value={settings.thumbnailSize}
        onChange={(v) => settings.update({ thumbnailSize: v })}
      />

        <button type="button" className="btn btn-ghost btn-sm mt-2" onClick={() => settings.reset()}>
          Reset Settings
        </button>
      </div>
    </div>
  )
}
