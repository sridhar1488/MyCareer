import type { components } from '../../api/schema';
import type { ReactNode } from 'react';
import { developmentLabels } from './DevelopmentFields';
import { cycleLabel } from '../../utils/labels';

import {formConfig,TextSections} from '../forms/config';
type Appraisal = components['schemas']['AppraisalResponse'];
export function SubmissionReview({ data, busy = false, submitDisabled = false, onBack, onSubmit, readOnly = false, children, title }: { data: Appraisal; busy?: boolean; submitDisabled?: boolean; onBack?: () => void; onSubmit?: () => void; readOnly?: boolean; children?: ReactNode; title?: string }) {
  const config = formConfig(data.form_definition);
  return <section className="panel submission-review"><p className="eyebrow">{readOnly ? 'SUBMITTED RESPONSES' : 'REVIEW BEFORE SUBMITTING'}</p><h2>{title ?? cycleLabel(data.cycle_title)}</h2>{!title && <p>{readOnly ? 'This is the preserved copy of your submission.' : 'Your entries will become read-only after submission.'} Your assigned reporting manager is <strong>{data.manager_name}</strong>.</p>}
    {([['Goals',data.goals],['Organizational contributions',data.contributions]] as const).map(([title,items]) => <section key={title}><h3>{title}</h3>{items.length ? items.map((item,i) => <div className="review-item" key={i}><strong>{i+1}. {item.description}</strong><p className="review-text">{item.employee_narrative || 'No achievement narrative entered.'}</p></div>) : <p className="muted">No entries.</p>}</section>)}
    {config.development_enabled && <><h3>{config.development_title}</h3>{developmentLabels.map(([key,label]) => <div className="review-item" key={key}><strong>{label}</strong><p className="review-text">{data.development[key] || 'Not provided.'}</p></div>)}</>}
    <TextSections config={config} owner="EMPLOYEE" answers={data.development.extra_answers}/>
    {children}
    <div className="action-bar">{onBack && <button className="button" disabled={busy} onClick={onBack}>{readOnly ? 'Close revision' : 'Back to editing'}</button>}{!readOnly && <button className="button primary" disabled={busy || submitDisabled} onClick={onSubmit}>{busy ? 'Submitting…' : 'Submit to reporting manager'}</button>}</div></section>;
}
