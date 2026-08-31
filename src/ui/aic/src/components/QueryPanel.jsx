import { useState } from 'react'
import { Search, Plus, X, Loader2 } from 'lucide-react'
import { MODELS, SEARCH_TYPES } from '../api/search'
import { useSearchStore } from '../stores/searchStore'
import { useRunSearch } from '../hooks/useRunSearch'

const TABS = [
  { value: SEARCH_TYPES.TEXT, label: 'Text' },
  { value: SEARCH_TYPES.IMAGE, label: 'Image' },
  { value: SEARCH_TYPES.TEMPORAL, label: 'Temporal' },
  { value: SEARCH_TYPES.SCROLL, label: 'Browse' },
]

export default function QueryPanel() {
  const store = useSearchStore()
  const { run, canRun } = useRunSearch()

  const [imagePreview, setImagePreview] = useState(null)
  // One entry per temporal event, joined with ". " for the backend. Kept in the
  // store so useRunSearch and the filter inputs see what this panel edits.
  const events = store.events
  const setEvents = (next) => store.setQuery({ events: next })

  const searching = store.status === 'loading'

  function handleFile(file) {
    if (!file) return
    const reader = new FileReader()
    reader.onload = () => {
      setImagePreview(reader.result)
      // The hub accepts a data: URI directly as image_path.
      store.setQuery({ imagePath: reader.result })
    }
    reader.readAsDataURL(file)
  }

  function handlePaste(e) {
    const item = [...(e.clipboardData?.items || [])].find((i) => i.type.startsWith('image/'))
    if (item) handleFile(item.getAsFile())
  }

  async function handleSubmit(e) {
    e.preventDefault()
    await run()
  }

  return (
    <div className="card bg-base-100 shadow-sm">
      <form className="card-body gap-4" onSubmit={handleSubmit}>
        <h2 className="card-title text-base">Query</h2>

        <div role="tablist" className="tabs tabs-boxed tabs-sm">
          {TABS.map((tab) => (
            <button
              key={tab.value}
              type="button"
              role="tab"
              className={`tab ${store.searchType === tab.value ? 'tab-active' : ''}`}
              onClick={() => store.setQuery({ searchType: tab.value })}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {store.searchType === SEARCH_TYPES.TEXT && (
          <textarea
            className="textarea textarea-bordered w-full h-28"
            placeholder="Describe the frame you're looking for... (Enter to search, Shift+Enter for a new line)"
            value={store.text}
            onChange={(e) => store.setQuery({ text: e.target.value })}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                handleSubmit(e)
              }
            }}
          />
        )}

        {store.searchType === SEARCH_TYPES.TEMPORAL && (
          <div className="flex flex-col gap-2">
            <p className="text-xs text-base-content/60">
              One event per line, in order. The main event is the one results are anchored to.
            </p>
            {events.map((event, i) => (
              <div key={i} className="flex items-center gap-2">
                <input
                  type="radio"
                  name="main-event"
                  className="radio radio-xs"
                  title="Main event"
                  checked={store.mainEventIndex === i}
                  onChange={() => store.setQuery({ mainEventIndex: i })}
                />
                <input
                  type="text"
                  className="input input-bordered input-sm flex-1"
                  placeholder={`Event ${i + 1}`}
                  value={event}
                  onChange={(e) =>
                    setEvents(events.map((v, j) => (j === i ? e.target.value : v)))
                  }
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      e.preventDefault()
                      handleSubmit(e)
                    }
                  }}
                />
                {events.length > 1 && (
                  <button
                    type="button"
                    className="btn btn-ghost btn-xs"
                    onClick={() => {
                      setEvents(events.filter((_, j) => j !== i))
                      if (store.mainEventIndex >= events.length - 1) {
                        store.setQuery({ mainEventIndex: 0 })
                      }
                    }}
                    aria-label={`Remove event ${i + 1}`}
                  >
                    <X size={14} />
                  </button>
                )}
              </div>
            ))}
            <button
              type="button"
              className="btn btn-ghost btn-xs self-start gap-1"
              onClick={() => setEvents([...events, ''])}
            >
              <Plus size={14} /> Add event
            </button>
          </div>
        )}

        {store.searchType === SEARCH_TYPES.IMAGE && (
          <div className="flex flex-col gap-2" onPaste={handlePaste}>
            <label
              className="border-2 border-dashed border-base-300 rounded-lg p-4 text-center text-sm text-base-content/60 cursor-pointer hover:border-primary transition-colors block"
              onDrop={(e) => {
                e.preventDefault()
                handleFile(e.dataTransfer.files?.[0])
              }}
              onDragOver={(e) => e.preventDefault()}
            >
              {imagePreview ? (
                <img src={imagePreview} alt="query preview" className="mx-auto max-h-32 rounded" />
              ) : (
                <span>Drag, paste, or click to choose an image</span>
              )}
              <input
                type="file"
                accept="image/*"
                className="hidden"
                onChange={(e) => handleFile(e.target.files?.[0])}
              />
            </label>
            <input
              type="text"
              placeholder="...or paste an image URL"
              className="input input-bordered input-sm w-full"
              onChange={(e) => {
                setImagePreview(e.target.value || null)
                store.setQuery({ imagePath: e.target.value })
              }}
            />
          </div>
        )}

        {store.searchType === SEARCH_TYPES.SCROLL && (
          <div className="flex flex-col gap-2">
            <p className="text-xs text-base-content/60">
              Browses every frame of the videos selected in Filters. Pick at least one video.
            </p>
            <p className="text-xs text-base-content/50">
              Returns every keyframe of the selected videos in order. Per-frame
              modes (duplicates / unique) are on each result card instead, since
              they address one specific frame.
            </p>
          </div>
        )}

        <fieldset className="fieldset">
          <legend className="fieldset-legend text-xs uppercase tracking-wide text-base-content/60">
            Model
          </legend>
          <div className="flex flex-col gap-1">
            {MODELS.map((m) => (
              <label
                key={m.value}
                className={`label justify-start gap-2 ${m.available ? 'cursor-pointer' : 'opacity-40 cursor-not-allowed'}`}
                title={m.available ? undefined : 'No Qdrant collection indexed for this model yet'}
              >
                <input
                  type="radio"
                  name="model"
                  className="radio radio-sm"
                  value={m.value}
                  disabled={!m.available}
                  checked={store.model === m.value}
                  onChange={() => store.setQuery({ model: m.value })}
                />
                <span className="label-text">{m.label}</span>
                {!m.available && <span className="badge badge-ghost badge-xs">no index</span>}
              </label>
            ))}
          </div>
        </fieldset>

        {store.status === 'error' && (
          <div className="alert alert-error text-sm py-2">{store.error}</div>
        )}

        <button type="submit" className="btn btn-primary mt-auto gap-2" disabled={!canRun}>
          {searching ? <Loader2 size={16} className="animate-spin" /> : <Search size={16} />}
          {searching ? 'Searching…' : 'Search'}
        </button>
      </form>
    </div>
  )
}
