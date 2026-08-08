export default function Thumbnail({ video, onClick }) {
  return (
    <div
      className="card bg-base-100 shadow-sm hover:shadow-md transition-shadow cursor-pointer"
      onClick={onClick}
    >
      <figure>
        <img src={video.thumbnail_url} alt={video.title} className="aspect-video w-full object-cover" />
      </figure>
      <div className="card-body p-3 gap-0.5">
        <p className="text-sm font-medium truncate">{video.title}</p>
        <p className="text-xs text-base-content/60">
          {video.video_id} · {video.timestamp}
        </p>
      </div>
    </div>
  )
}
