import { useState, type FormEvent } from 'react';
import type { components } from '../../api/schema';
import { CountedTextarea } from '../../components/CountedTextarea';
import { appraisalResponseLimit, isSingleCharacter } from '../../utils/appraisalTextLimits';
import { api, downloadFile } from '../../api/client';
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
type Row = components['schemas']['CalibrationQueueRow'];
type CalibrationEvent = {action: string; reason: string; actor_name: string; occurred_at: string; score: Score};
type Calibration = Pick<Row, 'id' | 'employee_name' | 'employee_id' | 'cycle_title' | 'manager_name' | 'manager_submitted_at' | 'version' | 'submitted_revision'> & {
  manager_evaluation: Evaluation; manager_score: Score; evaluation: Evaluation; score_preview: Score;
  employee_snapshot: {identity: Record<string, unknown>; form_definition: Record<string, unknown>; responses: components['schemas']['EmployeeResponses']};
  events: CalibrationEvent[];
};
type RatingSection = 'goals' | 'contributions' | 'competencies';

export function Calibrations() {
  const [query, setQuery] = useState('');
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [cycle, setCycle] = useState('');
  const [revision, setRevision] = useState(0);
  const [detail, setDetail] = useState<Calibration | null>(null);
  const [evaluation, setEvaluation] = useState<Evaluation | null>(null);
  const [reason, setReason] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [override, setOverride] = useState<{row: Row; score: string; reason: string} | null>(null);

  const params = new URLSearchParams({q: search, ...(cycle ? {cycle_id: cycle} : {})});
  const {data:queue,error:loadError,loading} = useApi<components['schemas']['CalibrationQueuePage']>(`/hr/calibrations?${params}&page=${page}`, revision);
  const {data:options,error:optionsError} = useApi<components['schemas']['MonitorOptions']>('/hr/monitor-options');
  const rows = queue?.items ?? [];
  const total = queue?.total ?? 0;
  function load(next = 1) { setError(''); setOverride(null); setPage(next); setRevision(value => value + 1); }

  async function download() {
    setBusy(true); setError('');
    try { await downloadFile(`/hr/calibrations/export/xlsx?${params}`, 'hr-calibration-queue.xlsx'); }
    catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }

  async function saveOverride(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!override || !override.reason.trim() || isSingleCharacter(override.reason)) return;
    const {row, score, reason} = override;
    setBusy(true); setError(''); setNotice('');
    try {
      await api(`/hr/calibrations/${row.id}/overall-score`, 'PUT', {
        expected_version: row.version, submitted_revision: row.submitted_revision,
        score: score === '' ? null : score, reason: reason.trim(),
      });
      load(page);
      setNotice(score === '' ? 'Calculated score restored.' : 'Overall score override saved. Approve when ready.');
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }

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

  async function approve(target: Pick<Row, 'id' | 'version' | 'submitted_revision'>) {
    setBusy(true); setError('');
    try {
      await api(`/hr/calibrations/${target.id}/approve`, 'POST', {
        expected_version: target.version, submitted_revision: target.submitted_revision,
      });
      setDetail(null); setEvaluation(null);
      setNotice('HR approved the evaluation. The manager can now release it to the employee.');
      load(1);
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }

  if (!detail) return <>
    {(error || loadError || optionsError) && <Feedback message={error || loadError || optionsError} />}{notice && <Feedback message={notice} success />}
    <section className="panel">
      <div className="section-heading"><h2>Waiting for HR approval</h2><div className="action-bar">
        <button className="button small" disabled={busy} onClick={() => load()}>Refresh</button>
        <button className="button small" disabled={busy || loading || !total} onClick={download}>Download calibration grid · Excel</button>
      </div></div>
      <p className="muted">The download includes all matching appraisals awaiting approval, across every page.</p>
      <form className="filters" onSubmit={e => { e.preventDefault(); setSearch(query.trim()); load(); }}>
        <label>Search employee or manager<input maxLength={150} value={query} onChange={e => setQuery(e.target.value)} /></label>
        <label>Appraisal cycle<select value={cycle} onChange={e => { setCycle(e.target.value); load(); }}><option value="">All cycles</option>{options?.cycles.map(option => <option key={option.id} value={option.id}>{option.label}</option>)}</select></label>
        <div className="action-bar"><button className="button" type="submit" disabled={busy}>Search</button></div>
      </form>
      <div className="table-scroll"><table className="calibration-grid"><thead><tr><th>Employee</th><th>Manager</th><th>Cycle and appraisal form</th><th>Manager score</th><th>Calibrated score</th><th>Approval</th></tr></thead><tbody>
        {rows.map(row => <tr key={row.id}>
          <td>{row.employee_name}<small>{row.employee_id} · {row.department}</small></td>
          <td>{row.manager_name}<small>{localDateTime(row.manager_submitted_at)}</small></td>
          <td>{row.cycle_title}<small>{row.form_name}</small></td>
          <td>{row.manager_overall}</td>
          <td><strong>{row.calibrated_overall}</strong>
            {row.calculated_overall != null && <small>HR override · Calculated {row.calculated_overall}</small>}
            {override?.row.id === row.id ? <form className="calibration-override" onSubmit={saveOverride}>
              <label>Overall score<input type="number" min={0} max={5} step={0.1} required={row.calculated_overall == null} disabled={busy} value={override.score} onChange={e => setOverride({...override, score: e.target.value})} /></label>
              {row.calculated_overall != null && <small>Clear the score to restore the calculated value.</small>}
              <label htmlFor="override-reason">Reason</label><CountedTextarea id="override-reason" rows={3} required maxLength={appraisalResponseLimit} disabled={busy} value={override.reason} onChange={e => setOverride({...override, reason: e.target.value})} />
              <div className="action-bar"><button className="button small primary" disabled={busy || !override.reason.trim() || isSingleCharacter(override.reason)}>Save score</button><button className="button small" type="button" disabled={busy} onClick={() => setOverride(null)}>Cancel</button></div>
            </form> : <button className="text-button calibration-override-trigger" disabled={busy} onClick={() => setOverride({row, score: row.calibrated_overall, reason: ''})}>Override score</button>}
          </td>
          <td><div className="calibration-actions">
            <button className="text-button" disabled={busy || override?.row.id === row.id} onClick={() => void open(row.id)}>Review and calibrate</button>
            <button className="button small primary" disabled={busy || override?.row.id === row.id} onClick={() => {
              if (window.confirm(`Approve ${row.employee_name}’s overall score of ${row.calibrated_overall} for manager release?`)) void approve(row);
            }}>Approve</button>
          </div></td>
        </tr>)}
      </tbody></table></div>
      {loading && <p role="status">Loading appraisals awaiting approval…</p>}
      {!loading && !loadError && !rows.length && <p>No matching appraisals are waiting for HR approval.</p>}
      {queue && <Pagination page={page} total={total} size={queue.page_size} onPage={load} />}
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
    <section className="panel"><p>Save your changes to recalculate the score preview.</p><label htmlFor="calibration-reason">Reason for calibration (required when you change ratings)</label><CountedTextarea id="calibration-reason" rows={4} maxLength={appraisalResponseLimit} value={reason} disabled={busy} onChange={e => setReason(e.target.value)} />
      <div className="action-bar"><button className="button" disabled={busy || isSingleCharacter(reason)} onClick={() => void save()}>Save calibration</button><button className="button primary" disabled={busy || evaluationChanged} onClick={() => { if (window.confirm('Approve this final score? The manager will be able to release it to the employee.')) void approve(detail); }}>Approve for manager release</button></div>
    </section>
    <section className="panel"><h2>Manager’s original submitted evaluation</h2><ReviewHistoryEntry evaluation={detail.manager_evaluation} competencies={competencyLabels} definition={definition} /><ScoreSummary score={detail.manager_score} /></section>
    {detail.events.length > 0 && <section className="panel"><h2>Calibration history</h2><ol className="history-list">{detail.events.map((event, index) => <li key={index}><strong>{event.action} · {event.actor_name}</strong><p>{localDateTime(event.occurred_at)} {event.reason}</p></li>)}</ol></section>}
  </>;
}
