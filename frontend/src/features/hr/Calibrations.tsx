import { useState } from 'react';
import type { components } from '../../api/schema';
import { api } from '../../api/client';
import { Feedback } from '../../components/Feedback';
import { Pagination } from '../../components/Pagination';
import { localDateTime } from '../../utils/dates';
import { formConfig } from '../forms/config';
import { Attachments } from '../appraisals/Attachments';
import { RatingFields } from '../reviews/RatingFields';
import { ScoreSummary } from '../reviews/ScoreSummary';
import { ReviewHistoryEntry } from '../reviews/ReviewHistoryEntry';
import { useApi } from '../../api/useApi';

type Evaluation = components['schemas']['EvaluationInput'];
type Rating = components['schemas']['RatingInput'];
type Score = components['schemas']['ScoreResult'];
type Row = {
  id: string; employee_name: string; employee_id: string; department: string; manager_name: string;
  cycle_title: string; state: string; version: number; submitted_revision: number; manager_submitted_at: string;
};
type CalibrationEvent = {action: string; reason: string; actor_name: string; occurred_at: string; score: Score};
type Calibration = Row & {
  manager_evaluation: Evaluation; manager_score: Score; evaluation: Evaluation; score_preview: Score;
  employee_snapshot: {identity: Record<string, unknown>; form_definition: Record<string, unknown>; responses: components['schemas']['EmployeeResponses']};
  events: CalibrationEvent[];
};
type RatingSection = 'goals' | 'contributions' | 'competencies';

export function Calibrations() {
  const [query, setQuery] = useState('');
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [revision, setRevision] = useState(0);
  const [detail, setDetail] = useState<Calibration | null>(null);
  const [evaluation, setEvaluation] = useState<Evaluation | null>(null);
  const [reason, setReason] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  const {data:queue,error:loadError} = useApi<{items: Row[]; total: number}>(`/hr/calibrations?q=${encodeURIComponent(search)}&page=${page}`, revision);
  const rows = queue?.items ?? [];
  const total = queue?.total ?? 0;
  function load(next = 1) { setError(''); setPage(next); setSearch(query); setRevision(value => value + 1); }

  async function open(id: string) {
    setBusy(true); setError('');
    try {
      const result = await api<Calibration>(`/hr/calibrations/${id}`);
      setDetail(result); setEvaluation(result.evaluation); setReason('');
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }

  async function save() {
    if (!detail || !evaluation) return;
    setBusy(true); setError(''); setNotice('');
    try {
      const result = await api<Calibration>(`/hr/calibrations/${detail.id}`, 'PUT', {
        expected_version: detail.version, submitted_revision: detail.submitted_revision, evaluation, reason,
      });
      setDetail(result); setEvaluation(result.evaluation); setReason('');
      setNotice('Calibration saved. The manager’s original evaluation remains preserved.');
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }

  async function approve() {
    if (!detail) return;
    setBusy(true); setError('');
    try {
      await api(`/hr/calibrations/${detail.id}/approve`, 'POST', {
        expected_version: detail.version, submitted_revision: detail.submitted_revision,
      });
      setDetail(null); setEvaluation(null);
      setNotice('HR approved the evaluation. The manager can now release it to the employee.');
      await load(1);
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }

  if (!detail) return <>
    {(error || loadError) && <Feedback message={error || loadError} />}{notice && <Feedback message={notice} success />}
    <section className="panel">
      <div className="section-heading"><h2>Waiting for HR approval</h2><button className="button small" onClick={() => void load(1)}>Refresh</button></div>
      <div className="filters"><label>Search employee<input value={query} onChange={e => setQuery(e.target.value)} onKeyDown={e => { if (e.key === 'Enter') void load(1); }} /></label><button className="button" onClick={() => void load(1)}>Search</button></div>
      <div className="table-scroll"><table><thead><tr><th>Employee</th><th>Appraisal cycle</th><th>Manager submission</th><th>Action</th></tr></thead><tbody>
        {rows.map(row => <tr key={row.id}><td>{row.employee_name}<small>{row.employee_id} · {row.department}</small></td><td>{row.cycle_title}</td><td>{row.manager_name}<small>{localDateTime(row.manager_submitted_at)}</small></td><td><button className="text-button" disabled={busy} onClick={() => void open(row.id)}>Review and calibrate</button></td></tr>)}
      </tbody></table></div>
      {!rows.length && <p>No appraisals are waiting for HR approval.</p>}
      <Pagination page={page} total={total} onPage={load} />
    </section>
  </>;

  const definition = detail.employee_snapshot.form_definition;
  const config = formConfig(definition);
  const content = detail.employee_snapshot.responses;
  const competencyLabels = config.competencies.map(item => item.label);
  const evaluationChanged = Boolean(evaluation && JSON.stringify(evaluation) !== JSON.stringify(detail.evaluation));

  function setRating(section: RatingSection, index: number, value: Rating) {
    if (!evaluation) return;
    setEvaluation({ ...evaluation, [section]: evaluation[section].map((entry, i) => i === index ? { ...entry, ...value, comment: entry.comment } : entry) });
  }

  return <>
    {error && <Feedback message={error} />}{notice && <Feedback message={notice} success />}
    <div className="action-bar"><button className="button" onClick={() => { setDetail(null); setEvaluation(null); void load(1); }}>Back to calibration queue</button><span className="status">HR review</span></div>
    <section className="panel"><h2>{detail.employee_name} · {detail.cycle_title}</h2><p>{detail.employee_id} · Manager: {detail.manager_name} · Submitted {localDateTime(detail.manager_submitted_at)}</p><p>Adjust individual ratings below. The app recalculates the score. Manager comments and the original manager submission stay preserved.</p></section>
    <Attachments appraisalId={detail.id} />
    {(['goals', 'contributions'] as const).map(section => {
      if (section === 'contributions' && !config.contributions_enabled) return null;
      return <section className="panel" key={section}><h2>{section === 'goals' ? config.goals_title : config.contributions_title}</h2>
        {content[section].map((item, index) => <div key={index}><h3>{item.description}</h3><p>{item.employee_narrative}</p>
          <p className="muted">Manager rating: {detail.manager_evaluation[section][index].rating ?? 'N/A'} · HR rating: {evaluation?.[section][index].rating ?? 'Not rated'}</p>
          <RatingFields id={`hr-${section}-${index}`} label={`Calibrated ${section === 'goals' ? 'goal' : 'contribution'} rating`} value={evaluation![section][index]} disabled={busy} commentReadOnly onChange={value => setRating(section, index, value)} />
        </div>)}
      </section>;
    })}
    {config.competencies_enabled && <section className="panel"><h2>{config.competencies_title}</h2>{config.competencies.map((item, index) => <div key={item.id}>
      <p className="muted">Manager rating: {detail.manager_evaluation.competencies[index].rating ?? 'N/A'} · HR rating: {evaluation?.competencies[index].rating ?? 'Not rated'}</p>
      <RatingFields id={`hr-comp-${index}`} label={item.label} allowNA={item.leadership} value={evaluation!.competencies[index]} disabled={busy} commentReadOnly onChange={value => setRating('competencies', index, value)} />
    </div>)}</section>}
    <section className="panel"><h2>Manager narrative</h2><ReviewHistoryEntry evaluation={detail.manager_evaluation} competencies={competencyLabels} definition={definition} /></section>
    <ScoreSummary score={detail.score_preview} />
    <section className="panel"><p>Save your changes to recalculate the score preview.</p><label htmlFor="calibration-reason">Reason for calibration (required when you change ratings)</label><textarea id="calibration-reason" rows={4} maxLength={2000} value={reason} disabled={busy} onChange={e => setReason(e.target.value)} />
      <div className="action-bar"><button className="button" disabled={busy} onClick={() => void save()}>Save calibration</button><button className="button primary" disabled={busy || evaluationChanged} onClick={() => { if (window.confirm('Approve this final score? The manager will be able to release it to the employee.')) void approve(); }}>Approve for manager release</button></div>
    </section>
    <section className="panel"><h2>Manager’s original submitted evaluation</h2><ReviewHistoryEntry evaluation={detail.manager_evaluation} competencies={competencyLabels} definition={definition} /><ScoreSummary score={detail.manager_score} /></section>
    {detail.events.length > 0 && <section className="panel"><h2>Calibration history</h2><ol className="history-list">{detail.events.map((event, index) => <li key={index}><strong>{event.action} · {event.actor_name}</strong><p>{localDateTime(event.occurred_at)} {event.reason}</p></li>)}</ol></section>}
  </>;
}
