import type { components } from '../../api/schema';
import { CountedTextarea } from '../../components/CountedTextarea';
import { appraisalResponseLimit } from '../../utils/appraisalTextLimits';
type Development = components['schemas']['DevelopmentInput'];
export const developmentLabels: [Exclude<keyof Development,'extra_answers'>,string][] = [
  ['business_achievements','Most important achievements and contributions to company / project success'],
  ['development_achievements','Personal and professional development achievements'],
  ['six_month_growth','Growth and development you would like to achieve in the next six months'],
  ['development_needs','Technical and personal development needs'],
  ['development_plan','Development plan for the forthcoming year'],
  ['support_requested','Support requested to meet your development needs'],
];
export function DevelopmentFields({ value, disabled, onChange, showErrors, title = "IV. Achievements and development" }: { title?: string; value: Development; disabled: boolean; onChange: (value: Development) => void; showErrors?: boolean }) {
  return <section className="panel appraisal-section development-fields">
    <h2>{title}</h2>
    <p className="muted">Reflect on the review period and your next steps. Enter a response or NA for each question before submitting.</p>
    {developmentLabels.map(([key, label]) => {
      const id = `development-${key}`;
      const invalid = showErrors && !value[key]?.trim();
      return <div key={key}>
        <label htmlFor={id}>{label}</label>
        {invalid && <small id={`${id}-error`} className="appraisal-field-error">Enter a response or NA.</small>}
        <CountedTextarea id={id} aria-invalid={invalid || undefined} aria-describedby={invalid ? `${id}-error` : undefined} disabled={disabled} rows={4} maxLength={appraisalResponseLimit} value={value[key] ?? ''} onChange={e => onChange({...value,[key]:e.target.value})} />
      </div>;
    })}
  </section>;
}
