export default function Pagination({ page, totalPages, onPrev, onNext }) {
  return (
    <div className="join">
      <button type="button" className="btn btn-sm join-item" onClick={onPrev} disabled={page <= 1}>
        «
      </button>
      <span className="btn btn-sm join-item pointer-events-none">
        {page} / {totalPages}
      </span>
      <button type="button" className="btn btn-sm join-item" onClick={onNext} disabled={page >= totalPages}>
        »
      </button>
    </div>
  )
}
