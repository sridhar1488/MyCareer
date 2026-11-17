import type { components } from '../../api/schema';
import { CountedTextarea } from '../../components/CountedTextarea';
import { FieldIssue, invalidField } from '../../components/FieldIssue';
import { appraisalHeaderLimit, appraisalResponseLimit, appraisalTextMinimum } from '../../utils/appraisalTextLimits';
export type Config = components['schemas']['FormConfig'];
export function formConfig(definition: Record<string, unknown>): Config {
  if (definition.form_config) {
    const config = definition.form_config as Config;
    return {
      ...config,
      goal_title_max_length: Math.max(appraisalTextMinimum, Math.min(config.goal_title_max_length ?? appraisalHeaderLimit, appraisalHeaderLimit)),
      goal_description_max_length: Math.max(appraisalTextMinimum, Math.min(config.goal_description_max_length ?? appraisalResponseLimit, appraisalResponseLimit)),
    };
  }
  return {name:'Workbook annual appraisal',goals_title:'Goals and job responsibilities',contributions_title:'Organizational contributions',competencies_title:'Professional competencies',development_title:'Achievements and development',goals_limit:100,goal_title_max_length:appraisalHeaderLimit,goal_description_max_length:appraisalResponseLimit,contributions_limit:3,contributions_enabled:true,competencies_enabled:true,development_enabled:true,weights:{goals:70,contributions:10,competencies:20},competencies:((definition.competencies ?? []) as string[]).map((label,i)=>({id:`competency-${i}`,label,leadership:i===10})),text_sections:[],section_order:['goals','contributions','competencies','development']};
}
export function TextSections({config,owner,answers={},disabled=false,onChange,sectionId,errors={}}:{
  config:Config; owner:'EMPLOYEE'|'MANAGER'; answers?:Record<string,string>; disabled?:boolean;
  onChange?:(v:Record<string,string>)=>void; sectionId?:string; errors?:Record<string,string>;
}) {
  return <>{config.text_sections?.filter(s => s.owner === owner && (!sectionId || sectionId === s.id)).map(s =>
    <section className="panel" key={s.id}><h2>{s.title}</h2>{s.questions.map(q => {
      const id = `question-${q.id}`;
      return <div key={q.id}>
        {onChange ? <>
          <label htmlFor={id}>{q.label}{q.required ? ' (required)' : ''}</label>
          <FieldIssue id={id} error={errors[id]} />
          <CountedTextarea id={id} {...invalidField(id, errors[id])} maxLength={appraisalResponseLimit} rows={4}
            disabled={disabled} value={answers[q.id] ?? ''} onChange={e => onChange({...answers,[q.id]:e.target.value})} />
        </> : <><strong>{q.label}</strong><p className="review-text">{answers[q.id] || 'Not provided.'}</p></>}
      </div>;
    })}</section>)}</>;
}
