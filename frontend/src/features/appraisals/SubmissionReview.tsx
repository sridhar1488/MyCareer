import type { components } from '../../api/schema';
import { developmentLabels } from './DevelopmentFields';

import {formConfig,TextSections} from '../forms/config';
type Appraisal = components['schemas']['AppraisalResponse'];
export function SubmissionReview({ data, busy, onBack, onSubmit, readOnly = false }: { data: Appraisal; busy: boolean; onBack: () => void; onSubmit: () => void; readOnly?: boolean }) {
  return <section className="panel submission-review"><p className="eyebrow">{readOnly ? 'SUBMITTED RESPONSES' : 'REVIEW BEFORE SUBMITTING'}</p><h2>{data.cycle_title}</h2><p>{readOnly ? 'This is the preserved copy of your submission.' : 'Your entries will become read-only after submission.'} Your assigned reporting manager is <strong>{data.manager_name}</strong>.</p>
    {([['Goals',data.goals],['Organizational contributions',data.contributions]] as const).map(([title,items]) => <section key={title}><h3>{title}</h3>{items.length ? items.map((item,i) => <div className="review-item" key={i}><strong>{i+1}. {item.description}</strong><p className="review-text">{item.employee_narrative || 'No achievement narrative entered.'}</p></div>) : <p className="muted">No entries.</p>}</section>)}
    <h3>Achievements and development</h3>{developmentLabels.map(([key,label]) => <div className="review-item" key={key}><strong>{label}</strong><p className="review-text">{data.development[key] || 'Not provided.'}</p></div>)}
    <TextSections config={formConfig(data.form_definition)} owner="EMPLOYEE" answers={data.development.extra_answers}/>
    <div className="action-bar"><button className="button" disabled={busy} onClick={onBack}>{readOnly ? 'Close revision' : 'Back to editing'}</button>{!readOnly && <button className="button primary" disabled={busy} onClick={onSubmit}>{busy ? 'Submitting…' : 'Submit to reporting manager'}</button>}</div></section>;
}
