import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { list } from '../api/dummy'
import { useSettingsStore } from '../stores/settingsStore'
import Thumbnail from './Thumbnail'
import FrameDetailModal from './FrameDetailModal'
import Pagination from './Pagination'

export default function VideoGrid() {
  const [selected, setSelected] = useState(null)
  const [page, setPage] = useState(1)
  const resultsPerPage = useSettingsStore((s) => s.resultsPerPage)
  const thumbnailSize = useSettingsStore((s) => s.thumbnailSize)

  const [prevResultsPerPage, setPrevResultsPerPage] = useState(resultsPerPage)
  if (resultsPerPage !== prevResultsPerPage) {
    setPrevResultsPerPage(resultsPerPage)
    setPage(1)
  }

  const { data, isLoading, isError } = useQuery({
    queryKey: ['videos'],
    queryFn: async () => {
      const res = await list()
      return res.data
    },
  })

  if (isLoading) {
    return (
      <div className="flex justify-center p-16">
        <span className="loading loading-spinner loading-lg" />
      </div>
    )
  }

  if (isError) {
    return <div className="alert alert-error">Failed to load videos.</div>
  }

  const totalPages = Math.max(1, Math.ceil(data.length / resultsPerPage))
  const pageItems = data.slice((page - 1) * resultsPerPage, page * resultsPerPage)

  return (
    <div className="flex flex-col gap-4">
      <div className="flex justify-center">
        <Pagination
          page={page}
          totalPages={totalPages}
          onPrev={() => setPage((p) => Math.max(1, p - 1))}
          onNext={() => setPage((p) => Math.min(totalPages, p + 1))}
        />
      </div>
      <div
        className="grid gap-4"
        style={{ gridTemplateColumns: `repeat(auto-fill, minmax(min(${thumbnailSize}px, 45vw), 1fr))` }}
      >
        {pageItems.map((video) => (
          <Thumbnail key={video.id} video={video} onClick={() => setSelected(video)} />
        ))}
      </div>
      
      <FrameDetailModal video={selected} onClose={() => setSelected(null)} />
    </div>
  )
}
