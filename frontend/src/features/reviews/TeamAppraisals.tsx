import { useState } from 'react';
import type { components } from '../../api/schema';
import { api } from '../../api/client';
import { useApi } from '../../api/useApi';
import { Feedback } from '../../components/Feedback';
import { Pagination } from '../../components/Pagination';
import { localDateTime } from '../../utils/dates';
import { ManagerReview } from './ManagerReview';
import { teamAppraisalParams } from './teamFilters';

export function TeamAppraisals({ initialStatus = '' }: { initialStatus?: string }) {
  const [q,setQ] = useState(''); const [state,setState] = useState(initialStatus); const [page,setPage] = useState(1); const [revision,setRevision] = useState(0);
  const [selected,setSelected] = useState<components['schemas']['ReviewResponse'] | null>(null); const [error,setError] = useState(''); const [busy,setBusy] = useState(false);
  const params = new URLSearchParams({q,page:String(page),...teamAppraisalParams(state)});
  const {data,error:loadError,loading} = useApi<components['schemas']['TeamPage']>(`/manager/appraisals?${params}`,revision);
  async function open(id:string) {setBusy(true);setError('');try{setSelected(await api(`/manager/appraisals/${id}`));}catch(e){setError((e as Error).message);}finally{setBusy(false);}}
  if(selected) return <ManagerReview initial={selected} onBack={() => {setSelected(null);setRevision(revision+1);}} />;
  return <>{(error || loadError) && <Feedback message={error || loadError} />}<section className="panel"><div className="section-heading"><h2>Assigned employee appraisals</h2><button className="button" onClick={() => setRevision(revision+1)}>Refresh</button></div>
    <div className="filters"><div><label htmlFor="team-search">Find an employee</label><input id="team-search" value={q} onChange={e => {setQ(e.target.value);setPage(1);}} /></div><div><label htmlFor="team-status">Workflow status</label><select id="team-status" value={state} onChange={e => {setState(e.target.value);setPage(1);}}><option value="">All statuses</option>{['DRAFT','SUBMITTED','UNDER_REVIEW','RETURNED_FOR_REVISION','HR_REVIEW','HR_APPROVED','RELEASED'].map(s => <option key={s}>{s}</option>)}<option value="READY_FOR_RELEASE">Ready for release</option></select></div></div>
    {loading && <p role="status">Loading assigned appraisals…</p>}{data && <><div className="table-scroll"><table><thead><tr><th>Employee / cycle</th><th>Status</th><th>Dates</th><th>Action</th></tr></thead><tbody>{data.items.map(a => <tr key={a.id}><td><strong>{a.employee_name}</strong><small>{a.employee_id} · {a.department}</small><small>{a.cycle_title}</small></td><td><span className="status">{a.state.replaceAll('_',' ')}</span><small>Submitted revision {a.submitted_revision}</small></td><td><small>Submitted {localDateTime(a.submitted_at)}</small><small>Deadline {localDateTime(a.submission_deadline)}</small></td><td>{a.submitted_revision > 0 ? <button className="button small" disabled={busy} onClick={() => open(a.id)}>Open review<span className="sr-only"> for {a.employee_name}</span></button> : <span className="muted">Waiting for submission</span>}</td></tr>)}</tbody></table></div>{data.total === 0 && <p>No assigned appraisals match these filters.</p>}<Pagination page={page} total={data.total} onPage={setPage} /></>}</section></>;
}
