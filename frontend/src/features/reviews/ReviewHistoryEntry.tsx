import type { components } from '../../api/schema';
import {formConfig,TextSections} from '../forms/config';
export function ReviewHistoryEntry({evaluation,competencies,definition}: {evaluation:components['schemas']['EvaluationInput'];competencies:string[];definition?:Record<string,unknown>}) {
  const config=definition?formConfig(definition):null;
  return <>{(['goals','contributions','competencies'] as const).map(section => <section key={section}><h4>{config ? config[`${section}_title`] : {goals:'Goals',contributions:'Organizational contributions',competencies:'Professional competencies'}[section]}</h4>{evaluation[section].map((r,i) => <p className="review-text" key={i}>{section === 'competencies' ? competencies[i] : `${section === 'goals' ? 'Goal' : 'Contribution'} ${i+1}`}: {r.not_applicable ? `N/A (${r.applicability_reason})` : r.rating ?? 'Not rated'} · {r.comment}</p>)}</section>)}{definition && <TextSections config={formConfig(definition)} owner="MANAGER" answers={evaluation.extra_answers}/>}<p className="review-text">Strengths: {evaluation.strengths}</p><p className="review-text">Improvements: {evaluation.improvements}</p></>;
}
