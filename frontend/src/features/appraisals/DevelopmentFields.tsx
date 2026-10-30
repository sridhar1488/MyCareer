import type { components } from '../../api/schema';
type Development = components['schemas']['DevelopmentInput'];
export const developmentLabels: [Exclude<keyof Development,'extra_answers'>,string][] = [
  ['business_achievements','Most important achievements and contributions to company / project success'],
  ['development_achievements','Personal and professional development achievements'],
  ['six_month_growth','Growth and development you would like to achieve in the next six months'],
  ['development_needs','Technical and personal development needs'],
  ['development_plan','Development plan for the forthcoming year'],
  ['support_requested','Support requested to meet your development needs'],
];
export function DevelopmentFields({ value, disabled, onChange, title = "IV. Achievements and development" }: { title?: string; value: Development; disabled: boolean; onChange: (value: Development) => void }) {
  return <section className="panel appraisal-section"><h2>{title}</h2><p className="muted">Reflect on the review period and your next steps. Discuss your development needs and support with your manager.</p>{developmentLabels.map(([key,label]) => <div key={key}><label htmlFor={`development-${key}`}>{label}</label><textarea id={`development-${key}`} disabled={disabled} rows={4} maxLength={10000} value={value[key] ?? ''} onChange={e => onChange({...value,[key]:e.target.value})} /></div>)}</section>;
}
