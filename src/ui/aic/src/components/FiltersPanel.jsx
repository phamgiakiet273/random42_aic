import { useQuery } from '@tanstack/react-query'
import { listVideoNames } from '../api/dummy'
import { useFiltersStore } from '../stores/filtersStore'

const BATCHES = [0, 1]

export default function FiltersPanel() {
  const filters = useFiltersStore()

  const { data: videoNames = [] } = useQuery({
    queryKey: ['videoNames'],
    queryFn: async () => {
      const res = await listVideoNames()
      return res.data
    },
  })

  const visibleVideoNames = videoNames.filter((name) =>
    name.toLowerCase().includes(filters.videoSearch.toLowerCase())
  )

  return (
    <div className="card bg-base-100 shadow-sm">
      <div className="card-body gap-4">
        <h2 className="card-title text-base">Filters</h2>

        <div>
          <p className="text-xs uppercase tracking-wide text-base-content/60 mb-1">Included Videos</p>
          <input
            type="text"
            placeholder="Search videos..."
            className="input input-bordered input-sm w-full mb-2"
            value={filters.videoSearch}
            onChange={(e) => filters.update({ videoSearch: e.target.value })}
          />
          <div className="border border-base-300 rounded-lg max-h-40 overflow-y-auto">
            {visibleVideoNames.map((name) => (
              <label key={name} className="label cursor-pointer justify-start gap-2 px-2 py-1 hover:bg-base-200">
                <input
                  type="checkbox"
                  className="checkbox checkbox-xs"
                  checked={filters.selectedVideos.includes(name)}
                  onChange={() => filters.toggleVideo(name)}
                />
                <span className="label-text text-xs">{name}</span>
              </label>
            ))}
          </div>
          <div className="flex gap-3 mt-2">
            {BATCHES.map((value) => (
              <label key={value} className="label cursor-pointer gap-1">
                <input
                  type="checkbox"
                  className="checkbox checkbox-sm"
                  checked={filters.batches.includes(value)}
                  onChange={() => filters.toggleBatch(value)}
                />
                <span className="label-text">Batch {value}</span>
              </label>
            ))}
          </div>
        </div>

        <div>
          <p className="text-xs uppercase tracking-wide text-base-content/60 mb-1">Excluded Frames</p>
          {filters.excludedFrames.length === 0 ? (
            <p className="text-xs text-base-content/50">No excluded frames yet.</p>
          ) : (
            <ul className="text-xs flex flex-col gap-1">
              {filters.excludedFrames.map((frame) => (
                <li key={frame.id} className="flex items-center justify-between bg-base-200 rounded px-2 py-1">
                  {frame.label}
                  <button
                    type="button"
                    className="btn btn-ghost btn-xs"
                    onClick={() => filters.removeExcludedFrame(frame.id)}
                  >
                    ×
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div>
          <p className="text-xs uppercase tracking-wide text-base-content/60 mb-1">Other Filters</p>
          <input
            type="text"
            placeholder="S2T filter..."
            className="input input-bordered input-sm w-full mb-2"
            value={filters.s2tFilter}
            onChange={(e) => filters.update({ s2tFilter: e.target.value })}
          />
          <div className="flex gap-2">
            <input
              type="text"
              placeholder="Start..."
              className="input input-bordered input-sm flex-1"
              value={filters.timeIn}
              onChange={(e) => filters.update({ timeIn: e.target.value })}
            />
            <input
              type="text"
              placeholder="End..."
              className="input input-bordered input-sm flex-1"
              value={filters.timeOut}
              onChange={(e) => filters.update({ timeOut: e.target.value })}
            />
          </div>
        </div>

        <button type="button" className="btn btn-ghost btn-sm mt-2" onClick={() => filters.reset()}>
          Reset All Filters
        </button>
      </div>
    </div>
  )
}
