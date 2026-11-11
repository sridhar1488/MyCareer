import { useEffect, useRef, useState } from 'react';
import type { components } from '../../api/schema';
import { api } from '../../api/client';
import { BackToTop } from '../../components/BackToTop';
import { Feedback } from '../../components/Feedback';
import { Pagination } from '../../components/Pagination';
import { localDateTime } from '../../utils/dates';
import { isSingleCharacter } from '../../utils/appraisalTextLimits';
import { NarrativeItems, narrativeStatus } from './NarrativeItems';
import { DevelopmentFields, developmentLabels } from './DevelopmentFields';
import { SubmissionReview } from './SubmissionReview';
import { markUnsaved } from '../../app/unsaved';
import { formConfig, TextSections } from '../forms/config';
import { ReleasedEvaluation } from '../reviews/ReleasedEvaluation';
import { Attachments } from './Attachments';

type Appraisal = components['schemas']['AppraisalResponse']; type Item = components['schemas']['ItemInput'];
type Notice = { message: string; kind: 'toast' | 'inline' };

function narrativeChanged(current: Item[], saved: Item[]) {
  const isEntered = (item: Item) => item.description.trim() || item.employee_narrative.trim();
  const entries = current.filter(isEntered);
  const savedEntries = saved.filter(isEntered);
  return entries.length !== savedEntries.length || entries.some((item, index) =>
    item.description !== savedEntries[index].description ||
    item.employee_narrative !== savedEntries[index].employee_narrative
  );
}

export function AppraisalForm({ initial, onBack }: { initial: Appraisal; onBack: () => void }) {
  const config = formConfig(initial.form_definition);
  const [data,setData] = useState(initial); const [goals,setGoals] = useState<Item[]>(initial.goals.length ? initial.goals : initial.editable ? [{description:'',employee_narrative:''}] : []);
  const [contributions,setContributions] = useState(initial.contributions); const [development,setDevelopment] = useState(initial.development);
  const [busy,setBusy] = useState(false); const [error,setError] = useState(''); const [notice,setNotice] = useState<Notice | null>(null); const [review,setReview] = useState(false);
  const [history,setHistory] = useState<components['schemas']['HistoryPage'] | null>(null); const [historyPage,setHistoryPage] = useState(1);
  const [snapshot,setSnapshot] = useState<components['schemas']['RevisionResponse'] | null>(null);
  const [showSubmissionErrors, setShowSubmissionErrors] = useState(false);
  const submissionSummary = useRef<HTMLDivElement>(null);
  const assessmentStart = useRef<HTMLButtonElement>(null);
  const answers = development.extra_answers ?? {};
  const savedAnswers = data.development.extra_answers ?? {};
  const dirty = narrativeChanged(goals, data.goals) || narrativeChanged(contributions, data.contributions) ||
    developmentLabels.some(([key]) => (development[key] ?? '') !== (data.development[key] ?? '')) ||
    Object.keys({...savedAnswers, ...answers}).some(key => (answers[key] ?? '') !== (savedAnswers[key] ?? ''));
  const goalStatuses = goals.map(narrativeStatus);
  const contributionStatuses = config.contributions_enabled ? contributions.map(narrativeStatus) : [];
  const needsGoals = goalStatuses.filter(status => status === 'complete').length < data.min_goals;
  const hasIncompleteRows = [...goalStatuses, ...contributionStatuses].some(
    status => status === 'description' || status === 'employee_narrative'
  );
  const hasIncompleteDevelopment = config.development_enabled &&
    developmentLabels.some(([key]) => !development[key]?.trim());
  const hasShortText = [...goals, ...(config.contributions_enabled ? contributions : [])]
    .some(item => isSingleCharacter(item.description) || isSingleCharacter(item.employee_narrative))
    || (config.development_enabled && developmentLabels.some(([key]) => isSingleCharacter(development[key] ?? '')))
    || Object.values(answers).some(isSingleCharacter);
  const submissionError = [
    needsGoals && `Complete at least ${data.min_goals} ${data.min_goals === 1 ? 'goal' : 'goals'} before submitting.`,
    hasIncompleteRows && 'Complete the highlighted goal or contribution fields.',
    hasIncompleteDevelopment && 'Enter a response or NA for each Achievements and development question.',
    hasShortText && 'Use at least 2 characters in each entered field. Enter NA if it does not apply.',
  ].filter(Boolean).join(' ');

  useEffect(() => { markUnsaved(dirty); return () => markUnsaved(false); }, [dirty]);
  useEffect(() => { const handler = (e: BeforeUnloadEvent) => { if (dirty) { e.preventDefault(); e.returnValue=''; } }; window.addEventListener('beforeunload',handler); return () => window.removeEventListener('beforeunload',handler); },[dirty]);
  useEffect(() => {
    if (!showSubmissionErrors) return;
    const summary = submissionSummary.current;
    const firstInvalid = summary?.parentElement?.querySelector<HTMLTextAreaElement>(
      'textarea[aria-invalid="true"]'
    );
    (firstInvalid ?? summary)?.focus();
  }, [showSubmissionErrors]);
  useEffect(() => {
    if (notice?.kind !== 'toast') return;
    const timeout = window.setTimeout(() => setNotice(null), 6000);
    return () => window.clearTimeout(timeout);
  }, [notice]);

  async function save(forReview = false) {
    if (forReview && hasShortText) {
      setError(''); setNotice(null); setShowSubmissionErrors(true);
      return;
    }
    if (forReview) setShowSubmissionErrors(false);
    if (!dirty) {
      if (forReview) { setError(''); setNotice(null); setReview(true); }
      return;
    }
    setBusy(true); setError(''); setNotice(null);
    try {
      const saved = await api<Appraisal>(`/appraisals/${data.id}/self-assessment`,'PUT',{expected_version:data.version,goals,contributions,development});
      setData(saved); setGoals(saved.goals); setContributions(saved.contributions); setDevelopment(saved.development);
      setNotice({message: 'Draft saved.', kind: forReview ? 'inline' : 'toast'});
      if (forReview) setReview(true);
    } catch(e) { setError((e as Error).message); } finally { setBusy(false); }
  }
  async function submit() {
    setError('');
    if (submissionError) {
      setNotice(null); setReview(false); setShowSubmissionErrors(true);
      return;
    }
    const confirmed = window.confirm(
      `Are you sure you want to submit your self-assessment to ${data.manager_name}?\n\n` +
      'Your responses will become read-only. You can edit them again if your reporting manager returns the assessment for revision.'
    );
    if (!confirmed) return;
    setBusy(true);
    try {
      const saved = await api<Appraisal>(`/appraisals/${data.id}/submit`,'POST',{expected_version:data.version});
      setData(saved); setReview(false); setNotice({message: 'Your appraisal has been submitted to your reporting manager.', kind: 'inline'}); setHistory(null);
    } catch(e) {setError((e as Error).message);} finally {setBusy(false);}
  }
  async function loadHistory(page = 1) { setError(''); try {setHistory(await api(`/appraisals/${data.id}/history?page=${page}`));setHistoryPage(page);} catch(e){setError((e as Error).message);} }
  async function revision(number = data.content_revision) {setError('');try {setSnapshot(await api(`/appraisals/${data.id}/revisions/${number}`));} catch(e){setError((e as Error).message);} }
  return <><div className="action-bar assessment-start"><button ref={assessmentStart} className="button" disabled={busy} onClick={() => { if (!dirty || window.confirm('Leave without saving your changes?')) onBack(); }}>Back to my appraisals</button><span className="status">{data.state.replaceAll('_',' ')}</span>{dirty && <span className="muted" role="status">Unsaved changes</span>}</div>
    <section className="appraisal-heading"><h2>{data.cycle_title}</h2><p className="muted">Reporting manager: {data.manager_name} · Submit by {localDateTime(data.submission_deadline)}</p><p className="muted">{data.min_goals} completed goal(s) required. Late submission is {data.allow_late_submission ? 'allowed' : 'blocked'}.</p></section>
    <section className="panel"><h3>Employee details for this cycle</h3><dl className="profile-grid">{[['employee_name','Employee'],['employee_id','Employee ID'],['department','Department'],['designation','Designation'],['country','Country']].map(([key,label]) => <div key={key}><dt>{label}</dt><dd>{String(data.identity_snapshot[key] || 'Not provided')}</dd></div>)}</dl></section>
    {error && <Feedback message={error} />}{notice?.kind === 'inline' && <Feedback message={notice.message} success />}
    <div className="draft-save-toast" role="status">
      {notice?.kind === 'toast' && <div className="feedback success">{notice.message}</div>}
    </div>
    {data.return_reason && <section className="panel"><h3>Changes requested by your manager</h3><p className="review-text">{data.return_reason}</p></section>}
    {data.state === 'RELEASED' && <ReleasedEvaluation appraisalId={data.id} />}
    <Attachments appraisalId={data.id} editable={data.editable}/>
    {review ? <SubmissionReview data={data} busy={busy} onBack={() => setReview(false)} onSubmit={submit} /> : <>
      <details className="panel instructions"><summary>Appraisal instructions</summary><p>Describe your responsibilities, achievements and additional organizational contributions. Enter NA for an achievement description that does not apply. Leave unused goal and contribution slots blank. Managers provide ratings and evaluation comments. You do not enter numerical self-ratings.</p><p>Add goals as needed. Up to three organizational contributions are supported. Save a draft at any time, then review your entries before submitting.</p></details>
      {showSubmissionErrors && submissionError && <div ref={submissionSummary} tabIndex={-1}><Feedback message={submissionError} /></div>}
      {config.section_order?.map(section => {
        if(section==='goals') return <NarrativeItems key={section} title={config.goals_title!} singular="Goal" items={goals} limit={config.goals_limit!} disabled={!data.editable || busy} onChange={setGoals} showErrors={showSubmissionErrors}
          textLimits={{description:config.goal_title_max_length, employee_narrative:config.goal_description_max_length}}/>;
        if(section==='contributions') return config.contributions_enabled && <NarrativeItems key={section} title={config.contributions_title!} singular="Contribution" items={contributions} limit={config.contributions_limit!} disabled={!data.editable || busy} onChange={setContributions} showErrors={showSubmissionErrors}/>;
        if(section==='competencies') return config.competencies_enabled && <section className="panel" key={section}><h2>{config.competencies_title}</h2><p>Your manager completes these ratings.</p><ul>{config.competencies.map(c=><li key={c.id}>{c.label}</li>)}</ul></section>;
        if(section==='development') return config.development_enabled && <DevelopmentFields key={section} title={config.development_title} value={development} disabled={!data.editable||busy} onChange={setDevelopment} showErrors={showSubmissionErrors}/>;
        return <TextSections key={section} config={config} sectionId={section} owner="EMPLOYEE" answers={development.extra_answers} disabled={!data.editable||busy} onChange={value=>setDevelopment({...development,extra_answers:value})}/>;
      })}
      {data.editable && <div className="panel action-bar sticky-actions"><button className="button save-draft-button" aria-busy={busy} disabled={busy || !dirty} onClick={() => save()}>{busy ? 'Saving…' : 'Save draft'}</button><button className="button primary" disabled={busy} onClick={() => save(true)}>Save and review submission</button></div>}
      {!data.editable && <p className="muted">{['HR_REVIEW','HR_APPROVED','FINALIZED','RELEASED'].includes(data.state) ? 'Your submitted appraisal is read-only. Your manager will share the approved result after HR review.' : 'Your submission is read-only. You can revise it if your reporting manager returns it for revision.'}</p>}
    </>}
    <section className="panel appraisal-workflow-history"><div className="action-bar"><button className="button" onClick={() => loadHistory()}>View workflow history</button>{data.content_revision > 0 && <button className="button" onClick={() => revision()}>View submitted revision {data.content_revision}</button>}</div>
      {data.last_draft_saved_at && <p className="muted">Last draft saved: <time dateTime={data.last_draft_saved_at}>{localDateTime(data.last_draft_saved_at)}</time></p>}
      {history && <><ol className="history-list">{history.items.map(e => <li key={e.id}><strong>{e.from_state ? `${e.from_state} → ` : ''}{e.to_state}</strong><p>{e.actor_name} · {localDateTime(e.occurred_at)}{e.reason ? ` · ${e.reason}` : ''}</p></li>)}</ol><Pagination page={historyPage} total={history.total} onPage={loadHistory} /></>}
      {data.content_revision > 1 && <><label htmlFor="revision-number">Earlier submitted revision</label><select id="revision-number" defaultValue="" onChange={e => { if(e.target.value) revision(Number(e.target.value)); }}><option value="">Choose a revision</option>{Array.from({length:data.content_revision},(_,i) => <option key={i+1} value={i+1}>Revision {i+1}</option>)}</select></>}
      {snapshot && <details open><summary>Submitted revision {snapshot.revision} · {localDateTime(snapshot.submitted_at)}</summary><SubmissionReview data={{...data,...snapshot.responses}} busy={false} readOnly onBack={() => setSnapshot(null)} onSubmit={() => {}} /></details>}
    </section>
    <BackToTop target={assessmentStart} />
  </>;
}
