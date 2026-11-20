import { useEffect, useState } from 'react';
import type { components } from '../../api/schema';
import { useApi } from '../../api/useApi';
import { Feedback } from '../../components/Feedback';
import { Pagination } from '../../components/Pagination';
import { localDateTime } from '../../utils/dates';
import { cycleLabel, statusLabel } from '../../utils/labels';
import { ManagerReview } from './ManagerReview';
import { teamAppraisalParams } from './teamFilters';

export function TeamAppraisals({ initialStatus = '', appraisalId, onOpen, userId }: { initialStatus?: string; appraisalId?: string; onOpen: (id?: string) => void; userId: string }) {
  const [search, setSearch] = useState('');
  const [q, setQ] = useState('');
  const [state,setState] = useState(initialStatus); const [page,setPage] = useState(1); const [revision,setRevision] = useState(0);
  useEffect(() => {
    const timer = window.setTimeout(() => { setQ(search.trim()); setPage(1); }, 300);
    return () => window.clearTimeout(timer);
  }, [search]);
  const params = new URLSearchParams({q,page:String(page),...teamAppraisalParams(state)});
  const {data,error:loadError,loading} = useApi<components['schemas']['TeamPage']>(appraisalId ? null : `/manager/appraisals?${params}`,revision);
  const detail = useApi<components['schemas']['ReviewResponse']>(appraisalId ? `/manager/appraisals/${encodeURIComponent(appraisalId)}` : null);
  if (appraisalId) {
    if (detail.data) return <ManagerReview key={detail.data.appraisal.id} initial={detail.data} userId={userId} onBack={() => onOpen()} />;
    return <><button className="button" onClick={() => onOpen()}>Back to team appraisals</button>
      {detail.error ? <Feedback message={detail.error} /> : <p role="status">Loading manager review…</p>}</>;
  }
  return <>{loadError && <Feedback message={loadError} />}<section className="panel"><div className="section-heading"><h2>Assigned employee appraisals</h2><button className="button" onClick={() => setRevision(revision+1)}>Refresh</button></div>
    <div className="filters"><div><label htmlFor="team-search">Find an employee</label><input id="team-search" value={search} maxLength={150} onChange={e => setSearch(e.target.value)} /></div><div><label htmlFor="team-status">Workflow status</label><select id="team-status" value={state} onChange={e => {setState(e.target.value);setPage(1);}}><option value="">All statuses</option>{['DRAFT','SUBMITTED','UNDER_REVIEW','RETURNED_FOR_REVISION','HR_REVIEW','HR_APPROVED','RELEASED'].map(s => <option key={s} value={s}>{statusLabel(s)}</option>)}<option value="READY_FOR_RELEASE">Ready for release</option></select></div></div>
    {(loading || search.trim() !== q) && <p role="status">Loading assigned appraisals…</p>}{data && search.trim() === q && <><div className="table-scroll"><table><thead><tr><th>Employee / cycle</th><th>Status</th><th>Dates</th><th>Action</th></tr></thead><tbody>{data.items.map(a => <tr key={a.id}><td><strong>{a.employee_name}</strong><small>{a.employee_id} · {a.department}</small><small>{cycleLabel(a.cycle_title)}</small></td><td><span className="status">{statusLabel(a.acknowledged_at ? 'ACKNOWLEDGED' : a.state)}</span><small>{a.submitted_revision > 0 ? `Submitted revision ${a.submitted_revision}` : 'Not submitted yet'}</small></td><td>{a.submitted_at && <small>Submitted {localDateTime(a.submitted_at)}</small>}<small>Deadline {localDateTime(a.submission_deadline)}</small></td><td>{a.submitted_revision > 0 ? <button className="button small" onClick={() => onOpen(a.id)}>Open review<span className="sr-only"> for {a.employee_name}</span></button> : <span className="muted">Waiting for submission</span>}</td></tr>)}</tbody></table></div>{data.total === 0 && <p>No assigned appraisals match these filters.</p>}<Pagination page={page} total={data.total} onPage={setPage} /></>}</section></>;
}
