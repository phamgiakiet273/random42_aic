import { useQuery } from '@tanstack/react-query'
import { list } from '../api/dummy'
import Thumbnail from './Thumbnail'

export default function VideoGrid() {
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

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-4 gap-4">
      {data.map((video) => (
        <Thumbnail key={video.id} video={video} />
      ))}
    </div>
  )
}
