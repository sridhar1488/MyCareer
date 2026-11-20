import { useState } from 'react';
import type { components } from '../../api/schema';
import { useApi } from '../../api/useApi';
import { Feedback } from '../../components/Feedback';
import { Pagination } from '../../components/Pagination';
import { WelcomeBanner } from '../../components/WelcomeBanner';
import { appraisalPeriod, localDateTime } from '../../utils/dates';
import { cycleLabel, statusLabel } from '../../utils/labels';
import { AppraisalForm } from './AppraisalForm';

export function MyAppraisals({ welcomeName, appraisalId, onOpen, profileCountry, userId }: { welcomeName?: string; appraisalId?: string; onOpen: (id?: string) => void; profileCountry?: string; userId: string }) {
  const [page,setPage] = useState(1); const [revision,setRevision] = useState(0);
  const {data,error:loadError} = useApi<components['schemas']['AppraisalPage']>(appraisalId ? null : `/me/appraisals?page=${page}`,revision);
  const detail = useApi<components['schemas']['AppraisalResponse']>(appraisalId ? `/appraisals/${encodeURIComponent(appraisalId)}` : null);
  if (appraisalId) {
    if (detail.data) return <AppraisalForm key={detail.data.id} initial={detail.data} userId={userId} onBack={() => onOpen()} profileCountry={profileCountry} />;
    return <><button className="button" onClick={() => onOpen()}>Back to my appraisals</button>
      {detail.error ? <Feedback message={detail.error} /> : <p role="status">Loading appraisal…</p>}</>;
  }
  return <>
    {welcomeName && <WelcomeBanner name={welcomeName} message="View your assigned appraisal cycles and continue your self-assessment." />}
    {loadError && <Feedback message={loadError} />}<section className="panel"><div className="section-heading"><h2>Your appraisal cycles</h2><button className="button small" onClick={() => setRevision(revision+1)}>Refresh</button></div>
    {!data && !loadError && <p role="status">Loading appraisals…</p>}{data?.items.map(a => <article className="appraisal-card" key={a.id}><div><span className="status">{statusLabel(a.acknowledged_at ? 'ACKNOWLEDGED' : a.state === 'DRAFT' && !a.started_at ? 'NOT_STARTED' : a.state)}</span><h3>{cycleLabel(a.cycle_title)}</h3><p className="muted">
      Appraisal period: {appraisalPeriod(a.period_start, a.period_end)}<br />
      Assigned reviewer: {a.manager_name}<br />
      Deadline: {localDateTime(a.submission_deadline)}{a.submitted_at && <><br />Submitted: {localDateTime(a.submitted_at)}</>}
    </p>{a.return_reason && <p className="review-text"><strong>Changes requested by your manager</strong><br />{a.return_reason}</p>}</div><button className="button primary" onClick={() => onOpen(a.id)}>{['DRAFT','RETURNED_FOR_REVISION'].includes(a.state) ? 'Open self-assessment' : 'View appraisal'}</button></article>)}
    {data?.total === 0 && <div className="empty-state"><h3>No appraisal cycle assigned yet</h3><p className="muted">Your HR team will assign your appraisal after your reporting manager is set.</p></div>}
    {data && (page > 1 || data.total > data.page_size) && <Pagination page={page} total={data.total} size={data.page_size} onPage={setPage} />}</section></>;
}
