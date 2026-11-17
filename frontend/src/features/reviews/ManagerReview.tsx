import { useEffect, useRef, useState } from 'react';
import type { components } from '../../api/schema';
import { BackToTop } from '../../components/BackToTop';
import { CountedTextarea } from '../../components/CountedTextarea';
import { FieldIssue, invalidField } from '../../components/FieldIssue';
import { appraisalResponseLimit, isSingleCharacter } from '../../utils/appraisalTextLimits';
import { api } from '../../api/client';
import { markUnsaved } from '../../app/unsaved';
import { useDraftSnapshot, useRecoveredDraft } from '../../app/draftRecovery';
import { Feedback } from '../../components/Feedback';
import { Pagination } from '../../components/Pagination';
import { localDateTime } from '../../utils/dates';
import { cycleLabel, statusLabel, competencyLabel } from '../../utils/labels';
import { developmentLabels } from '../appraisals/DevelopmentFields';
import { RatingFields } from './RatingFields';
import { ReviewHistoryEntry } from './ReviewHistoryEntry';
import { formConfig,TextSections } from '../forms/config';
import { ScoreSummary } from './ScoreSummary';
import { Attachments } from '../appraisals/Attachments';
import { RevisionComparison, restoreUnchangedRatings } from './RevisionComparison';
import { reviewFieldErrors } from './reviewValidation';
type Review = components['schemas']['ReviewResponse']; type Evaluation = components['schemas']['EvaluationInput'];
type DraftSnapshot = {version: number; revision: number; evaluation: Evaluation; reason: string};

export function ManagerReview({initial,onBack,userId}: {initial:Review;onBack:() => void;userId:string}) {
  const recoveryKey = `manager:${initial.appraisal.id}`;
  const recovered = useRecoveredDraft<DraftSnapshot>(recoveryKey, userId);
  const restored = recovered?.version === initial.appraisal.version &&
    recovered.revision === initial.submitted_revision && ['SUBMITTED','UNDER_REVIEW'].includes(initial.appraisal.state)
    ? recovered : undefined;
  const [previousCopy, setPreviousCopy] = useState(restored ? undefined : recovered);
  const [data,setData] = useState(initial); const [evaluation,setEvaluation] = useState(restored?.evaluation ?? initial.evaluation);
  const [busy,setBusy] = useState(false);
  const [error,setError] = useState(''); const [notice,setNotice] = useState(restored ? 'Your unsaved review edits were recovered.' : '');
  const [returning,setReturning] = useState(Boolean(restored?.reason)); const [reason,setReason] = useState(restored?.reason ?? '');
  const [history,setHistory] = useState<components['schemas']['ReviewEventPage'] | null>(null); const [historyPage,setHistoryPage] = useState(1);
  const [confirming,setConfirming] = useState<'finalize'|'release'|null>(null); const [meeting,setMeeting] = useState(false);
  const [showIssues, setShowIssues] = useState(false);
  const assessmentStart = useRef<HTMLButtonElement>(null);
  const reviewForm = useRef<HTMLDivElement>(null);
  const config=formConfig(data.appraisal.form_definition);
  const a = data.appraisal; const editable = ['SUBMITTED','UNDER_REVIEW'].includes(a.state);
  const inputDisabled = !editable || busy || confirming !== null;
  const dirty = JSON.stringify(evaluation) !== JSON.stringify(data.evaluation);
  const pendingEdits = dirty || Boolean(reason.trim());
  const hasUnsavedWork = pendingEdits || Boolean(previousCopy);
  const issues = showIssues ? reviewFieldErrors(evaluation, config) : {};
  const issueCount = Object.keys(issues).length;
  const restorable = editable ? restoreUnchangedRatings(data, evaluation) : null;
  useDraftSnapshot<DraftSnapshot>(recoveryKey, pendingEdits
    ? {version: a.version, revision: data.submitted_revision, evaluation, reason} : previousCopy);
  useEffect(() => {markUnsaved(hasUnsavedWork);return () => markUnsaved(false);},[hasUnsavedWork]);
  useEffect(() => {const handler = (e:BeforeUnloadEvent) => {if(hasUnsavedWork){e.preventDefault();e.returnValue='';}};window.addEventListener('beforeunload',handler);return () => window.removeEventListener('beforeunload',handler);},[hasUnsavedWork]);
  function update(value:Evaluation) {setEvaluation(value);setNotice('');setError('');}
  function focusIssue() {
    reviewForm.current?.querySelector<HTMLElement>('[aria-invalid="true"]')?.focus();
  }
  useEffect(() => { if (showIssues) focusIssue(); }, [showIssues]);

  function requestSignOff() {
    setError('');
    if (Object.keys(reviewFieldErrors(evaluation, config)).length) {
      if (showIssues) focusIssue();
      else setShowIssues(true);
      return;
    }
    if (dirty || a.state !== 'UNDER_REVIEW') {
      setError('Save your draft before submitting it to HR.');
      return;
    }
    if (!data.score_preview || data.validation_errors.length) {
      setError(data.validation_errors.join(' ') || 'The saved review has no score preview. Check the ratings and comments.');
      return;
    }
    setShowIssues(false);
    setConfirming('finalize');
  }
  async function command(action:string,method='POST',extra:object={}) {
    if (busy) return;
    setBusy(true);setError('');setNotice('');
    try {
      const saved = await api<Review>(`/manager/appraisals/${a.id}/${action}`,method,{expected_version:a.version,submitted_revision:data.submitted_revision,...extra});
      setData(saved); setEvaluation(saved.evaluation);
      if (action !== 'review') { setReturning(false); setReason(''); }
      setConfirming(null); setMeeting(false); setHistory(null);
      setNotice(action === 'finalize' ? 'Evaluation submitted to HR for calibration and approval.' :
        action === 'release' ? 'Evaluation released to the employee.' :
        action === 'return' ? 'Appraisal returned. The employee can revise their responses.' :
        action === 'begin' ? 'Review started.' : 'Manager review draft saved.');
    }
    catch(e){setError((e as Error).message);}finally{setBusy(false);}
  }
  async function loadHistory(page=1) {setError('');try{setHistory(await api(`/manager/appraisals/${a.id}/review-history?page=${page}`));setHistoryPage(page);}catch(e){setError((e as Error).message);}}
  return <div ref={reviewForm}><div className="action-bar assessment-start"><button ref={assessmentStart} className="button" disabled={busy} onClick={onBack}>Back to team appraisals</button><span className="status">{statusLabel(a.state)}</span>{pendingEdits && <span role="status">Unsaved review input</span>}</div>
    <section className="panel"><h2>{String(a.identity_snapshot.employee_name)} · {cycleLabel(a.cycle_title)}</h2><p className="muted">Submitted revision {data.submitted_revision} · {localDateTime(a.submitted_at)}</p><p>Employee responses below are the preserved submission.{editable && ' Use Return for revision to request changes.'}</p></section>
    {!editable && error && <Feedback message={error} />}{!editable && notice && <Feedback message={notice} success />}
    {previousCopy && <section className="panel"><h3>Recovered input from revision {previousCopy.revision}</h3>
      <p>The review changed while you were signed out. Check these earlier edits before reapplying them.</p>
      <details><summary>Show recovered ratings and comments</summary>
        <ReviewHistoryEntry evaluation={previousCopy.evaluation} competencies={a.form_definition.competencies as string[]} definition={a.form_definition} />
        {previousCopy.reason && <p className="review-text">Return reason: {previousCopy.reason}</p>}
      </details>
      <button className="button small" onClick={() => setPreviousCopy(undefined)}>Dismiss copy</button>
    </section>}
    {editable && data.submitted_revision > 1 && !data.draft_is_current && <section className="panel">
      <p role="status">The employee submitted a new revision. Ratings and comments start fresh for this revision. Any earlier saved evaluations are available in manager review history.</p>
      {restorable && <><p>You can restore earlier ratings and comments for unchanged goals and contributions. Review the restored entries before saving.</p>
        <button className="button" disabled={inputDisabled} onClick={() => update(restorable)}>Restore unchanged ratings and comments</button></>}
    </section>}
    {a.return_reason && <section className="panel"><h3>Reason sent to the employee</h3><p className="review-text">{a.return_reason}</p></section>}
    <RevisionComparison review={data} />
    {a.content_revision > 0 && a.state !== 'RETURNED_FOR_REVISION' && <Attachments appraisalId={a.id}/>}
    {a.state === 'HR_REVIEW' && <p className="panel">Your manager evaluation is with HR for calibration and approval. After HR approves it, discuss the approved evaluation with the employee, then release the scores.</p>}
    {a.state === 'SUBMITTED' && <div className="action-bar"><button className="button primary" disabled={busy || hasUnsavedWork || returning} onClick={() => command('begin')}>Begin review</button></div>}
    {a.state === 'RETURNED_FOR_REVISION' && <p className="panel">The employee is revising their submission. A new submission starts a fresh review; previous drafts remain in manager review history.</p>}
    {config.section_order?.map(section=>{
      if(section==='goals'||section==='contributions'){
        if(section==='contributions'&&!config.contributions_enabled)return null;
        return <section className="panel" key={section}><h2>{section==='goals'?config.goals_title:config.contributions_title}</h2>{data.employee_responses[section].length===0&&<p className="muted">No entries were submitted.</p>}{data.employee_responses[section].map((item,index)=><div key={index}><h3>{index+1}. {item.description}</h3><p className="review-text">{item.employee_narrative}</p><RatingFields id={`${section}-${index}`} label={`${section==='goals'?'Goal':'Contribution'} ${index+1} evaluation`} value={evaluation[section][index]} errors={issues} disabled={inputDisabled} onChange={value=>update({...evaluation,[section]:evaluation[section].map((old,i)=>i===index?value:old)})}/></div>)}</section>;
      }
      if(section==='competencies')return config.competencies_enabled&&<section className="panel" key={section}><h2>{config.competencies_title}</h2>{(a.form_definition.competencies as string[]).map((label,index)=><RatingFields key={index} id={`competency-${index}`} allowNA={config.competencies[index]?.leadership} label={competencyLabel(label)} value={evaluation.competencies[index]} errors={issues} disabled={inputDisabled} onChange={value=>update({...evaluation,competencies:evaluation.competencies.map((old,i)=>i===index?value:old)})}/>)}</section>;
      if(section==='development')return config.development_enabled&&<section className="panel" key={section}><h2>{config.development_title}</h2>{developmentLabels.map(([key,label])=><div className="review-item" key={key}><strong>{label}</strong><p className="review-text">{data.employee_responses.development[key]||'Not provided.'}</p></div>)}</section>;
      return <div key={section}><TextSections config={config} sectionId={section} owner="EMPLOYEE" answers={data.employee_responses.development.extra_answers}/><TextSections config={config} sectionId={section} owner="MANAGER" answers={evaluation.extra_answers} errors={issues} disabled={inputDisabled} onChange={answers=>update({...evaluation,extra_answers:answers})}/></div>;
    })}
    <section className="panel"><h2>Manager evaluation</h2>
      <label htmlFor="strengths">What the employee did particularly well</label>
      <FieldIssue id="strengths" error={issues.strengths} />
      <CountedTextarea id="strengths" {...invalidField('strengths', issues.strengths)} rows={5} maxLength={appraisalResponseLimit} disabled={inputDisabled} value={evaluation.strengths ?? ''} onChange={e => update({...evaluation,strengths:e.target.value})} />
      <label htmlFor="improvements">How the employee could be more effective</label>
      <FieldIssue id="improvements" error={issues.improvements} />
      <CountedTextarea id="improvements" {...invalidField('improvements', issues.improvements)} rows={5} maxLength={appraisalResponseLimit} disabled={inputDisabled} value={evaluation.improvements ?? ''} onChange={e => update({...evaluation,improvements:e.target.value})} />
    </section>
    <section className="panel"><h2>Scoring policy</h2><p>Goals 70% · Contributions 10% · Competencies 20%. An empty contributions section scores zero with its weight retained. Every populated applicable item requires a whole-number rating and supporting comment. Only leadership can be N/A with a reason.</p>{editable && !data.score_preview && !dirty && <p className="muted">A score preview is available once the required ratings and comments are complete and saved.</p>}{editable && dirty && <p role="status">Save manager draft to update the score preview.</p>}{!dirty && editable && data.validation_errors.length > 0 && <details><summary>Items needed before finalization ({data.validation_errors.length})</summary><ul>{data.validation_errors.map(message => <li key={message}>{message}</li>)}</ul></details>}</section>
    {!dirty && data.score_preview && <ScoreSummary score={data.score_preview} />}
    {data.final_result && <section className="panel"><h2>HR approved evaluation</h2><p>Approved {localDateTime(data.final_result.finalized_at)}</p><p>{data.final_result.released_at ? `Released ${localDateTime(data.final_result.released_at)}` : 'Awaiting your release to the employee.'}</p><p>{data.final_result.acknowledged_at ? `Employee receipt acknowledged ${localDateTime(data.final_result.acknowledged_at)}` : 'Employee receipt not yet acknowledged.'}</p>{a.state === 'HR_APPROVED' && <button className="button primary" disabled={busy || Boolean(confirming)} onClick={() => setConfirming('release')}>Release to employee</button>}</section>}
    {confirming && <section className="panel"><h2>{confirming === 'finalize' ? 'Submit evaluation to HR' : 'Release evaluation to employee'}</h2><p>{confirming === 'finalize' ? 'Your submitted responses, ratings, comments and score will be preserved for HR calibration. After HR approves, you can discuss the approved evaluation with the employee before releasing the result.' : 'After discussing the HR-approved evaluation with the employee, confirm the meeting to release the scores and comments.'}</p>{confirming === 'release' && <label className="choice"><input type="checkbox" checked={meeting} onChange={e => setMeeting(e.target.checked)} disabled={busy} />I confirm I discussed this HR-approved evaluation with the employee</label>}<div className="action-bar"><button className="button primary" disabled={busy || dirty || (confirming === 'release' && !meeting)} onClick={() => command(confirming,'POST',confirming === 'release' ? {review_meeting_confirmed:meeting} : {})}>{confirming === 'finalize' ? 'Confirm submission to HR' : 'Confirm meeting and release'}</button><button className="button" disabled={busy} onClick={() => setConfirming(null)}>Cancel sign-off</button></div></section>}
    {returning && <section className="panel"><h2>Return to employee</h2><p>Save any manager draft before returning.</p><label htmlFor="return-reason">Reason for revision</label><CountedTextarea id="return-reason" rows={4} maxLength={appraisalResponseLimit} disabled={busy} value={reason} onChange={e => setReason(e.target.value)} /><div className="action-bar"><button className="button primary" disabled={busy || !reason.trim() || isSingleCharacter(reason) || dirty} onClick={() => command('return','POST',{reason})}>Confirm return</button><button className="button" disabled={busy} onClick={() => {setReturning(false);setReason('');}}>Cancel return</button></div></section>}
    <section className="panel"><button className="button" onClick={() => loadHistory()}>View manager review history</button>{history && <><ol className="history-list">{history.items.map(event => <li key={event.id}><strong>{statusLabel(event.action)} · employee revision {event.submitted_revision}</strong><p>{localDateTime(event.occurred_at)}</p>{event.reason && <p className="review-text">{event.reason}</p>}{event.evaluation && <details><summary>{event.action === 'SUBMITTED_FOR_HR' ? 'Manager submission preserved for HR review' : event.action === 'FINALIZED' ? 'Preserved finalized evaluation' : 'Preserved manager draft'}</summary><ReviewHistoryEntry evaluation={event.evaluation} competencies={a.form_definition.competencies as string[]} definition={a.form_definition} /></details>}</li>)}</ol><Pagination page={historyPage} total={history.total} onPage={loadHistory} /></>}</section>
    {editable && <div className="panel sticky-actions manager-review-actions">
      {issueCount > 0 && <Feedback message={`Complete the ${issueCount} highlighted ${issueCount === 1 ? 'field' : 'fields'} before submitting to HR.`} />}
      {error && <Feedback message={error} />}
      {notice && <Feedback message={notice} success />}
      <div className="action-bar">
        <button className="button primary" aria-busy={busy} disabled={!dirty || busy || Boolean(confirming)}
          onClick={() => command('review','PUT',{evaluation})}>Save manager draft</button>
        <button className="button" disabled={busy || returning || Boolean(confirming)} onClick={() => setReturning(true)}>Return for revision</button>
        <button className="button primary" disabled={busy || returning || Boolean(confirming)}
          onClick={requestSignOff}>Submit to HR for approval</button>
      </div>
    </div>}
    <BackToTop target={assessmentStart} />
  </div>;
}
