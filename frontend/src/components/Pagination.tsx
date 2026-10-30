export function Pagination({ page, total, size = 25, onPage }: { page: number; total: number; size?: number; onPage: (page: number) => void }) {
  const pages = Math.max(1, Math.ceil(total / size));
  return <div className="pagination"><span>{total} result{total === 1 ? '' : 's'} · Page {page} of {pages}</span><div>
    <button type="button" className="button small" disabled={page <= 1} onClick={() => onPage(page - 1)}>Previous</button>
    <button type="button" className="button small" disabled={page >= pages} onClick={() => onPage(page + 1)}>Next</button>
  </div></div>;
}
