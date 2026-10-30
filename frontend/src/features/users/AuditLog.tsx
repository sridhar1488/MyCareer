import { useState } from 'react';
import type { components } from '../../api/schema';
import { useApi } from '../../api/useApi';
import { Feedback } from '../../components/Feedback';
import { Pagination } from '../../components/Pagination';
import { localDateTime } from '../../utils/dates';

export function AuditLog() {
  const [q, setQ] = useState(''); const [page, setPage] = useState(1);
  const { data, error } = useApi<components['schemas']['AuditPage']>(`/admin/audit-events?page=${page}&q=${encodeURIComponent(q)}`);
  return <section className="panel"><h2>Account administration history</h2><label htmlFor="audit-search">Filter event type</label><input id="audit-search" value={q} onChange={e => { setQ(e.target.value); setPage(1); }} placeholder="For example, admin.user_created" />
    {error && <Feedback message={error} />}{!data && !error && <p role="status">Loading audit history…</p>}{data && <><div className="table-scroll"><table><thead><tr><th>When</th><th>Event</th><th>Actor</th><th>Account / resource</th><th>Details</th></tr></thead><tbody>{data.items.map(e => <tr key={e.id}><td>{localDateTime(e.occurred_at)}</td><td>{e.action}</td><td>{e.actor_id ?? 'Local operator / system'}</td><td>{e.resource_id ?? '—'}</td><td><code>{JSON.stringify(e.details)}</code></td></tr>)}</tbody></table></div><Pagination page={page} total={data.total} onPage={setPage} /></>}</section>;
}
