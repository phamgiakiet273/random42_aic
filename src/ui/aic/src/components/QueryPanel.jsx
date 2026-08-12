import { useState } from 'react'

const MODELS = [
  { value: 'SIGLIP_ALPHA', label: 'SIGLIP Alpha' },
  { value: 'TEMPORAL_SIGLIP_ALPHA', label: 'Temporal Alpha' },
  { value: 'SIGLIP_BETA', label: 'SIGLIP Beta' },
  { value: 'TEMPORAL_SIGLIP_BETA', label: 'Temporal Beta' },
]

export default function QueryPanel() {
  const [queryType, setQueryType] = useState('text')
  const [query, setQuery] = useState('')
  const [model, setModel] = useState(MODELS[0].value)
  const [imageUrl, setImageUrl] = useState('')
  const [imagePreview, setImagePreview] = useState(null)

  function handleFile(file) {
    if (!file) return
    const reader = new FileReader()
    reader.onload = () => setImagePreview(reader.result)
    reader.readAsDataURL(file)
  }

  function handleDrop(e) {
    e.preventDefault()
    handleFile(e.dataTransfer.files?.[0])
  }

  function handleSubmit(e) {
    e.preventDefault()
    // Search execution isn't wired up yet — UI/config only for now.
  }

  return (
    <div className="card bg-base-100 shadow-sm">
      <form className="card-body gap-4" onSubmit={handleSubmit}>
        <h2 className="card-title text-base">Query</h2>

        <div className="join">
          <button
            type="button"
            className={`btn join-item btn-sm ${queryType === 'text' ? 'btn-active' : ''}`}
            onClick={() => setQueryType('text')}
          >
            Text
          </button>
          <button
            type="button"
            className={`btn join-item btn-sm ${queryType === 'image' ? 'btn-active' : ''}`}
            onClick={() => setQueryType('image')}
          >
            Image
          </button>
        </div>

        {queryType === 'text' ? (
          <textarea
            className="textarea textarea-bordered w-full h-28"
            placeholder="Text query here..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        ) : (
          <div className="flex flex-col gap-2">
            <label
              className="border-2 border-dashed border-base-300 rounded-lg p-4 text-center text-sm text-base-content/60 cursor-pointer hover:border-primary transition-colors block"
              onDrop={handleDrop}
              onDragOver={(e) => e.preventDefault()}
            >
              {imagePreview ? (
                <img src={imagePreview} alt="preview" className="mx-auto max-h-32 rounded" />
              ) : (
                <span>Drag & drop an image, or click to browse</span>
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
              placeholder="or paste an image URL..."
              className="input input-bordered input-sm w-full"
              value={imageUrl}
              onChange={(e) => setImageUrl(e.target.value)}
            />
          </div>
        )}

        <fieldset className="fieldset">
          <legend className="fieldset-legend text-xs uppercase tracking-wide text-base-content/60">Model</legend>
          <div className="flex flex-col gap-1">
            {MODELS.map((m) => (
              <label key={m.value} className="label cursor-pointer justify-start gap-2">
                <input
                  type="radio"
                  name="model"
                  className="radio radio-sm"
                  value={m.value}
                  checked={model === m.value}
                  onChange={() => setModel(m.value)}
                />
                <span className="label-text">{m.label}</span>
              </label>
            ))}
          </div>
        </fieldset>

        <button type="submit" className="btn btn-primary mt-auto">
          Search
        </button>
      </form>
    </div>
  )
}
