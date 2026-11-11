import { useState } from 'react';
import type { components } from '../../api/schema';
import { api } from '../../api/client';
import { useApi } from '../../api/useApi';
import { Feedback } from '../../components/Feedback';
import { Pagination } from '../../components/Pagination';
import { WelcomeBanner } from '../../components/WelcomeBanner';
import { appraisalPeriod, localDateTime } from '../../utils/dates';
import { AppraisalForm } from './AppraisalForm';

export function MyAppraisals({ welcomeName }: { welcomeName?: string }) {
  const [page,setPage] = useState(1); const [revision,setRevision] = useState(0); const [error,setError] = useState(''); const [busy,setBusy] = useState(false);
  const [selected,setSelected] = useState<components['schemas']['AppraisalResponse'] | null>(null);
  const {data,error:loadError} = useApi<components['schemas']['AppraisalPage']>(`/me/appraisals?page=${page}`,revision);
  async function open(id:string) {setBusy(true);setError('');try {const appraisal = await api<components['schemas']['AppraisalResponse']>(`/appraisals/${id}`); setSelected(appraisal); window.scrollTo({ top: 0, left: 0, behavior: 'instant' });} catch(e){setError((e as Error).message);}finally{setBusy(false);}}
  if(selected) return <AppraisalForm key={selected.id} initial={selected} onBack={() => {setSelected(null);setRevision(revision+1);}} />;
  return <>
    {welcomeName && <WelcomeBanner name={welcomeName} message="View your assigned appraisal cycles and continue your self-assessment." />}
    {(error || loadError) && <Feedback message={error || loadError} />}<section className="panel"><div className="section-heading"><h2>Your appraisal cycles</h2><button className="button small" onClick={() => setRevision(revision+1)}>Refresh</button></div>
    {!data && !loadError && <p role="status">Loading appraisals…</p>}{data?.items.map(a => <article className="appraisal-card" key={a.id}><div><span className="status">{a.state === 'DRAFT' && !a.started_at ? 'Not started' : a.state.replaceAll('_',' ')}</span><h3>{a.cycle_title}</h3><p className="muted">
      Appraisal period: {appraisalPeriod(a.period_start, a.period_end)}<br />
      Assigned reviewer: {a.manager_name}<br />
      Deadline: {localDateTime(a.submission_deadline)}{a.submitted_at && <><br />Submitted: {localDateTime(a.submitted_at)}</>}
    </p></div><button className="button primary" disabled={busy} onClick={() => open(a.id)}>{['DRAFT','RETURNED_FOR_REVISION'].includes(a.state) ? 'Open self-assessment' : 'View appraisal'}</button></article>)}
    {data?.total === 0 && <div className="empty-state"><h3>No appraisal cycle assigned yet</h3><p className="muted">Your HR team will assign your appraisal after your reporting manager is set.</p></div>}
    {data && (page > 1 || data.total > data.page_size) && <Pagination page={page} total={data.total} size={data.page_size} onPage={setPage} />}</section></>;
}
