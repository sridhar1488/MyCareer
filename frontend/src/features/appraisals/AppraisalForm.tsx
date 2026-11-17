import { useEffect, useRef, useState } from 'react';
import type { components } from '../../api/schema';
import { api, ApiError } from '../../api/client';
import { BackToTop } from '../../components/BackToTop';
import { Feedback } from '../../components/Feedback';
import { Pagination } from '../../components/Pagination';
import { localDateTime } from '../../utils/dates';
import { cycleLabel, statusLabel, competencyLabel } from '../../utils/labels';
import { isSingleCharacter } from '../../utils/appraisalTextLimits';
import { NarrativeItems, narrativeStatus } from './NarrativeItems';
import { DevelopmentFields, developmentLabels } from './DevelopmentFields';
import { SubmissionReview } from './SubmissionReview';
import { markUnsaved } from '../../app/unsaved';
import { useDraftSnapshot, useRecoveredDraft } from '../../app/draftRecovery';
import { formConfig, TextSections } from '../forms/config';
import { ReleasedEvaluation } from '../reviews/ReleasedEvaluation';
import { Attachments } from './Attachments';

type Appraisal = components['schemas']['AppraisalResponse']; type Item = components['schemas']['ItemInput'];
type Notice = { message: string; kind: 'toast' | 'inline' };
type Draft = Pick<Appraisal, 'goals' | 'contributions' | 'development'>;
type DraftSnapshot = {version: number; edits?: Draft; copy: string};

function narrativeChanged(current: Item[], saved: Item[]) {
  const isEntered = (item: Item) => item.description.trim() || item.employee_narrative.trim();
  const entries = current.filter(isEntered);
  const savedEntries = saved.filter(isEntered);
  return entries.length !== savedEntries.length || entries.some((item, index) =>
    item.description !== savedEntries[index].description ||
    item.employee_narrative !== savedEntries[index].employee_narrative
  );
}

function draftCopy(draft: Draft, questions: {id: string; label: string}[]) {
  return [
    ...draft.goals.map((item, i) => `Goal ${i + 1}\n${item.description}\n${item.employee_narrative}`),
    ...draft.contributions.map((item, i) => `Contribution ${i + 1}\n${item.description}\n${item.employee_narrative}`),
    ...developmentLabels.map(([key, label]) => `${label}\n${draft.development[key] ?? ''}`),
    ...questions.map(({id, label}) => `${label}\n${draft.development.extra_answers?.[id] ?? ''}`),
  ].join('\n\n');
}

export function AppraisalForm({ initial, onBack, profileCountry, userId }: { initial: Appraisal; onBack: () => void; profileCountry?: string; userId: string }) {
  const config = formConfig(initial.form_definition);
  const employeeQuestions = config.text_sections?.filter(section => section.owner === 'EMPLOYEE')
    .flatMap(section => section.questions) ?? [];
  const recoveryKey = `employee:${initial.id}`;
  const recovered = useRecoveredDraft<DraftSnapshot>(recoveryKey, userId);
  const restored = initial.editable && initial.version === recovered?.version ? recovered.edits : undefined;
  const start = restored ?? initial;
  const [data,setData] = useState(initial); const [goals,setGoals] = useState<Item[]>(start.goals.length ? start.goals : initial.editable ? [{description:'',employee_narrative:''}] : []);
  const [contributions,setContributions] = useState(start.contributions); const [development,setDevelopment] = useState(start.development);
  const [busy,setBusy] = useState(false); const [error,setError] = useState(''); const [notice,setNotice] = useState<Notice | null>(null); const [review,setReview] = useState(false);
  const [attachmentsBusy, setAttachmentsBusy] = useState(false);
  const [attachmentsReady, setAttachmentsReady] = useState(false);
  const [conflict, setConflict] = useState(false);
  const [recovery, setRecovery] = useState(() => [
    recovered?.edits && !restored ? draftCopy(recovered.edits, employeeQuestions) : '',
    recovered?.copy,
  ].filter(Boolean).join('\n\n'));
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [history,setHistory] = useState<components['schemas']['HistoryPage'] | null>(null); const [historyPage,setHistoryPage] = useState(1);
  const [snapshot,setSnapshot] = useState<components['schemas']['RevisionResponse'] | null>(null);
  const [showSubmissionErrors, setShowSubmissionErrors] = useState(false);
  const submissionSummary = useRef<HTMLDivElement>(null);
  const requestError = useRef<HTMLDivElement>(null);
  const assessmentStart = useRef<HTMLButtonElement>(null);
  const answers = development.extra_answers ?? {};
  const savedAnswers = data.development.extra_answers ?? {};
  const dirty = narrativeChanged(goals, data.goals) || narrativeChanged(contributions, data.contributions) ||
    developmentLabels.some(([key]) => (development[key] ?? '') !== (data.development[key] ?? '')) ||
    Object.keys({...savedAnswers, ...answers}).some(key => (answers[key] ?? '') !== (savedAnswers[key] ?? ''));
  const goalStatuses = goals.map(narrativeStatus);
  const contributionStatuses = config.contributions_enabled ? contributions.map(narrativeStatus) : [];
  const needsGoals = goalStatuses.filter(status => status === 'complete').length < data.min_goals;
  const hasBlankGoal = goalStatuses.includes('empty');
  const hasIncompleteRows = [...goalStatuses, ...contributionStatuses].some(
    status => status === 'description' || status === 'employee_narrative'
  );
  const hasIncompleteDevelopment = config.development_enabled &&
    developmentLabels.some(([key]) => !development[key]?.trim());
  const missingAnswers = employeeQuestions.filter(question => question.required && !answers[question.id]?.trim());
  const hasShortText = [...goals, ...(config.contributions_enabled ? contributions : [])]
    .some(item => isSingleCharacter(item.description) || isSingleCharacter(item.employee_narrative))
    || (config.development_enabled && developmentLabels.some(([key]) => isSingleCharacter(development[key] ?? '')))
    || Object.values(answers).some(isSingleCharacter);
  const submissionError = [
    needsGoals && `Complete at least ${data.min_goals} ${data.min_goals === 1 ? 'goal' : 'goals'} before submitting.`,
    hasBlankGoal && 'Complete or remove the blank goal before submitting.',
    hasIncompleteRows && 'Complete the highlighted goal or contribution fields.',
    hasIncompleteDevelopment && 'Enter a response or NA for each Achievements and development question.',
    ...missingAnswers.map(question => `Complete: ${question.label}.`),
    hasShortText && 'Use at least 2 characters in each entered field. Enter NA if it does not apply.',
  ].filter(Boolean).join(' ');

  const hasUnsavedWork = dirty || Boolean(recovery);
  useDraftSnapshot<DraftSnapshot>(recoveryKey, hasUnsavedWork ? {
    version: data.version, edits: dirty ? {goals, contributions, development} : undefined, copy: recovery,
  } : undefined);
  useEffect(() => { markUnsaved(hasUnsavedWork); return () => markUnsaved(false); }, [hasUnsavedWork]);
  useEffect(() => { if (error) requestError.current?.focus(); }, [error]);
  useEffect(() => { const handler = (e: BeforeUnloadEvent) => { if (hasUnsavedWork) { e.preventDefault(); e.returnValue=''; } }; window.addEventListener('beforeunload',handler); return () => window.removeEventListener('beforeunload',handler); },[hasUnsavedWork]);
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

  function showRequestError(cause: unknown) {
    if (cause instanceof ApiError) {
      setConflict(cause.code === 'VERSION_CONFLICT');
      setFieldErrors(Object.fromEntries(cause.fields.map(({field, message}) => [field, message])));
    }
    setError((cause as Error).message);
  }
  function setSaved(saved: Appraisal) {
    setData(saved);
    setGoals(saved.goals.length || !saved.editable ? saved.goals : [{description:'', employee_narrative:''}]);
    setContributions(saved.contributions);
    setDevelopment(saved.development);
  }
  async function reloadLatest() {
    setBusy(true);
    try {
      const saved = await api<Appraisal>(`/appraisals/${data.id}`);
      if (dirty) {
        const content = draftCopy({goals, contributions, development}, employeeQuestions);
        setRecovery(content);
      }
      setSaved(saved); setReview(false); setConflict(false); setError(''); setFieldErrors({});
      setShowSubmissionErrors(false); setHistory(null); setSnapshot(null);
      setNotice({message:'Latest saved version loaded.', kind:'inline'});
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }
  async function save(forReview = false) {
    if (busy || attachmentsBusy || conflict) return;
    if (forReview && submissionError) {
      setError(''); setNotice(null); setShowSubmissionErrors(true);
      submissionSummary.current?.focus();
      return;
    }
    if (forReview) { setShowSubmissionErrors(false); setAttachmentsReady(false); }
    if (!dirty) {
      if (forReview) { setError(''); setNotice(null); setReview(true); }
      return;
    }
    setBusy(true); setError(''); setNotice(null); setFieldErrors({});
    try {
      const saved = await api<Appraisal>(`/appraisals/${data.id}/self-assessment`,'PUT',{expected_version:data.version,goals,contributions,development});
      setSaved(saved);
      setNotice({message: 'Draft saved.', kind: forReview ? 'inline' : 'toast'});
      if (forReview) setReview(true);
    } catch(e) { showRequestError(e); } finally { setBusy(false); }
  }
  async function submit() {
    if (busy || conflict || !attachmentsReady) return;
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
    } catch(e) {showRequestError(e);} finally {setBusy(false);}
  }
  async function loadHistory(page = 1) { setError(''); try {setHistory(await api(`/appraisals/${data.id}/history?page=${page}`));setHistoryPage(page);} catch(e){setError((e as Error).message);} }
  async function revision(number = data.content_revision) {setError('');try {setSnapshot(await api(`/appraisals/${data.id}/revisions/${number}`));} catch(e){setError((e as Error).message);} }
  const snapshotCountry = data.identity_snapshot.country;
  const recordedCountry = typeof snapshotCountry === 'string' ? snapshotCountry.trim() : '';
  const country = recordedCountry || profileCountry || 'Not provided';
  return <><div className="action-bar assessment-start"><button ref={assessmentStart} className="button" disabled={busy || attachmentsBusy} onClick={onBack}>Back to my appraisals</button><span className="status">{statusLabel(data.state === 'DRAFT' && !data.started_at ? 'NOT_STARTED' : data.state)}</span>{dirty && <span className="muted" role="status">Unsaved changes</span>}</div>
    <section className="appraisal-heading"><h2>{cycleLabel(data.cycle_title)}</h2><p className="muted">Reporting manager: {data.manager_name} · Submit by {localDateTime(data.submission_deadline)}</p><p className="muted">{data.min_goals} completed goal(s) required. Late submission is {data.allow_late_submission ? 'allowed' : 'blocked'}.</p></section>
    {data.return_reason && <section className="panel"><h3>Changes requested by your manager</h3><p className="review-text">{data.return_reason}</p></section>}
    <section className="panel"><h3>Employee details for this cycle</h3><dl className="profile-grid">{[['employee_name','Employee'],['employee_id','Employee ID'],['department','Department'],['designation','Designation'],['country','Country']].map(([key,label]) => <div key={key}><dt>{label}</dt><dd>{key === 'country' ? country : String(data.identity_snapshot[key] || 'Not provided')}</dd></div>)}</dl></section>
    {error && <div ref={requestError} tabIndex={-1}><Feedback message={conflict ? 'This appraisal changed in another window. Your latest request was not saved.' : error} />
      {conflict && <button className="button" disabled={busy} onClick={() => void reloadLatest()}>Load latest version{dirty ? ' and keep a copy of my edits' : ''}</button>}
    </div>}{notice?.kind === 'inline' && <Feedback message={notice.message} success />}
    {restored && dirty && <Feedback message="Your unsaved edits were recovered. Review them and save your draft." success />}
    {recovery && <section className="panel"><h3>Recovered edits</h3><p>Copy your edits into the latest version where they still apply, then save again. This copy is available while this appraisal is open.</p>
      <label htmlFor="recovered-assessment">Previous unsaved responses</label><textarea id="recovered-assessment" readOnly rows={8} value={recovery} />
      <button className="button" onClick={() => setRecovery('')}>Dismiss copy</button></section>}
    <div className="draft-save-toast" role="status">
      {notice?.kind === 'toast' && <div className="feedback success">{notice.message}</div>}
    </div>
    {data.state === 'RELEASED' && <ReleasedEvaluation appraisalId={data.id} />}
    {review ? <SubmissionReview data={data} busy={busy} submitDisabled={conflict || !attachmentsReady} onBack={() => setReview(false)} onSubmit={submit}>
      <Attachments appraisalId={data.id} forSubmission onReviewReady={setAttachmentsReady} />
    </SubmissionReview> : <>
      <Attachments appraisalId={data.id} editable={data.editable} disabled={busy} onBusyChange={setAttachmentsBusy} />
      <details className="panel instructions"><summary>Appraisal instructions</summary><p>Describe your responsibilities, achievements and additional organizational contributions. Enter NA for an achievement description that does not apply. Complete or remove any blank goals before submitting. Managers provide ratings and evaluation comments.</p><p>Add goals as needed. Up to three organizational contributions are supported. You can save a partial draft and return to it later.</p></details>
      {showSubmissionErrors && submissionError && <div ref={submissionSummary} tabIndex={-1}><Feedback message={submissionError} /></div>}
      {config.section_order?.map(section => {
        if(section==='goals') return <NarrativeItems key={section} title={config.goals_title!} singular="Goal" items={goals} limit={config.goals_limit!} disabled={!data.editable || busy} onChange={items => {setGoals(items);setFieldErrors({});}} showErrors={showSubmissionErrors} fieldErrors={fieldErrors}
          textLimits={{description:config.goal_title_max_length, employee_narrative:config.goal_description_max_length}}/>;
        if(section==='contributions') return config.contributions_enabled && <NarrativeItems key={section} title={config.contributions_title!} singular="Contribution" items={contributions} limit={config.contributions_limit!} disabled={!data.editable || busy} onChange={items => {setContributions(items);setFieldErrors({});}} showErrors={showSubmissionErrors} fieldErrors={fieldErrors}/>;
        if(section==='competencies') return config.competencies_enabled && <section className="panel" key={section}><h2>{config.competencies_title}</h2><p>Your manager completes these ratings.</p><ul>{config.competencies.map(c=><li key={c.id}>{competencyLabel(c.label)}</li>)}</ul></section>;
        if(section==='development') return config.development_enabled && <DevelopmentFields key={section} title={config.development_title} value={development} disabled={!data.editable||busy} onChange={setDevelopment} showErrors={showSubmissionErrors}/>;
        return <TextSections key={section} config={config} sectionId={section} owner="EMPLOYEE" answers={development.extra_answers} disabled={!data.editable||busy} onChange={value=>setDevelopment({...development,extra_answers:value})}/>;
      })}
      {data.editable && <div className="panel action-bar sticky-actions"><button className="button save-draft-button" aria-busy={busy} disabled={busy || attachmentsBusy || conflict || !dirty} onClick={() => save()}>{busy ? 'Saving…' : 'Save draft'}</button><button className="button primary" disabled={busy || attachmentsBusy || conflict} onClick={() => save(true)}>Save and review submission</button></div>}
      {!data.editable && <p className="muted">{['HR_REVIEW','HR_APPROVED','FINALIZED','RELEASED'].includes(data.state) ? 'Your submitted appraisal is read-only. Your manager will share the approved result after HR review.' : 'Your submission is read-only. You can revise it if your reporting manager returns it for revision.'}</p>}
    </>}
    <section className="panel appraisal-workflow-history"><div className="action-bar"><button className="button" onClick={() => loadHistory()}>View workflow history</button>{data.content_revision > 0 && <button className="button" onClick={() => revision()}>View submitted revision {data.content_revision}</button>}</div>
      {data.last_draft_saved_at && <p className="muted">Last draft saved: <time dateTime={data.last_draft_saved_at}>{localDateTime(data.last_draft_saved_at)}</time></p>}
      {history && <><ol className="history-list">{history.items.map(e => <li key={e.id}><strong>{e.from_state ? `${statusLabel(e.from_state)} → ` : ''}{statusLabel(e.to_state)}</strong><p>{e.actor_name} · {localDateTime(e.occurred_at)}{e.reason ? ` · ${e.reason}` : ''}</p></li>)}</ol><Pagination page={historyPage} total={history.total} onPage={loadHistory} /></>}
      {data.content_revision > 1 && <><label htmlFor="revision-number">Earlier submitted revision</label><select id="revision-number" defaultValue="" onChange={e => { if(e.target.value) revision(Number(e.target.value)); }}><option value="">Choose a revision</option>{Array.from({length:data.content_revision},(_,i) => <option key={i+1} value={i+1}>Revision {i+1}</option>)}</select></>}
      {snapshot && <details open><summary>Submitted revision {snapshot.revision} · {localDateTime(snapshot.submitted_at)}</summary><SubmissionReview data={{...data,...snapshot.responses}} busy={false} readOnly onBack={() => setSnapshot(null)} onSubmit={() => {}} /></details>}
    </section>
    <BackToTop target={assessmentStart} />
  </>;
}
