import { useState } from 'react';
import type { components } from '../../api/schema';
import { api } from '../../api/client';
import { useApi } from '../../api/useApi';
import { Feedback } from '../../components/Feedback';
import { Pagination } from '../../components/Pagination';
import { localDateTime } from '../../utils/dates';
import { CycleEditor } from './CycleEditor';

type Cycle = components['schemas']['CycleResponse'];
export function Cycles() {
  const [editor, setEditor] = useState<Cycle | 'new' | null>(null); const [page, setPage] = useState(1); const [revision, setRevision] = useState(0);
  const [activating, setActivating] = useState<Cycle | null>(null); const [error, setError] = useState(''); const [notice, setNotice] = useState(''); const [busy, setBusy] = useState(false);
  const { data, error: loadError } = useApi<components['schemas']['CyclePage']>(`/cycles?page=${page}`, revision);
  async function activate() {
    if (!activating) return; setBusy(true); setError('');
    try { await api(`/cycles/${activating.id}/activate`, 'POST', { expected_version: activating.version }); setActivating(null); setNotice('Cycle activated. Personal appraisals have been assigned to the selected employees.'); setRevision(revision+1); }
    catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }
  if (editor) return <CycleEditor cycle={editor === 'new' ? undefined : editor} onCancel={() => setEditor(null)} onSaved={() => { setEditor(null); setNotice('Draft cycle saved. Review settings before activation.'); setRevision(revision+1); }} />;
  return <>{notice && <Feedback message={notice} success />}{(error || loadError) && <Feedback message={error || loadError} />}
    {activating && <section className="panel"><h2>Activate {activating.title}?</h2><p>Assign {activating.participant_ids.length} appraisals with a minimum of {activating.min_goals} completed goals. Deadline: {localDateTime(activating.submission_deadline)}. Late submission: {activating.allow_late_submission ? 'allowed' : 'blocked'}.</p><p>Each participant must have an active reporting manager. Their identities, reviewer and form version will be preserved for this cycle.</p><div className="action-bar"><button className="button primary" disabled={busy} onClick={activate}>{busy ? 'Activating…' : 'Confirm activation'}</button><button className="button" disabled={busy} onClick={() => setActivating(null)}>Cancel</button></div></section>}
    <section className="panel"><div className="section-heading"><p className="muted section-intro">Create cycles and assign appraisal forms to employees.</p><button className="button primary" onClick={() => { setError(''); setEditor('new'); }}>Create cycle</button></div>
      {!data && !loadError && <p role="status">Loading cycles…</p>}{data && <><div className="table-scroll"><table><thead><tr><th>Cycle</th><th>Period / deadline</th><th>Participants / rules</th><th>Status / actions</th></tr></thead><tbody>{data.items.map(c => <tr key={c.id}><td><strong>{c.title}</strong></td><td>{c.period_start} – {c.period_end}<small>Submit by {localDateTime(c.submission_deadline)}</small></td><td>{c.participant_ids.length} participants<small>{c.min_goals} minimum goals · late submission {c.allow_late_submission ? 'allowed' : 'blocked'}</small></td><td><span className="status">{c.state}</span>{c.state === 'DRAFT' && <div className="row-actions"><button className="text-button" onClick={() => { setError(''); setEditor(c); }}>Edit draft</button><button className="text-button" onClick={() => { setError(''); setActivating(c); }}>Activate cycle</button></div>}</td></tr>)}</tbody></table></div>{data.total === 0 && <p>No cycles have been created. Create a draft cycle to get started.</p>}<Pagination page={page} total={data.total} onPage={setPage} /></>}</section></>;
}
