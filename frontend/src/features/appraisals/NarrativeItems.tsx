import type { components } from '../../api/schema';
import { CountedTextarea } from '../../components/CountedTextarea';
import { appraisalHeaderLimit, appraisalResponseLimit } from '../../utils/appraisalTextLimits';

type Item = components['schemas']['ItemInput'];
const defaultLimits = {description: appraisalHeaderLimit, employee_narrative: appraisalResponseLimit};

export function narrativeStatus(item: Item): 'empty' | 'complete' | keyof Item {
  if (item.description.trim()) return item.employee_narrative.trim() ? 'complete' : 'employee_narrative';
  return item.employee_narrative.trim() ? 'description' : 'empty';
}

export function NarrativeItems({ title, singular, items, limit, disabled, onChange, textLimits, showErrors, fieldErrors = {} }: { title: string; singular: string; items: Item[]; limit: number; disabled: boolean; onChange: (items: Item[]) => void; textLimits?: Record<keyof Item, number>; showErrors?: boolean; fieldErrors?: Record<string, string> }) {
  function update(index: number, key: keyof Item, value: string) { onChange(items.map((item,i) => i === index ? { ...item, [key]: value } : item)); }
  const limits = textLimits ?? defaultLimits;
  const isGoal = singular === 'Goal';
  const hasBlankGoal = isGoal && items.some(item => narrativeStatus(item) === 'empty');
  const itemName = singular.toLowerCase();
  const addLabel = `Add ${itemName}`;
  const fields = [
    {key: 'description', suffix: 'description', label: isGoal ? 'Responsibility / goal description' : 'Contribution area', rows: 3},
    {key: 'employee_narrative', suffix: 'narrative', label: 'Achievements and self-assessment', rows: 5},
  ] as const;
  return <section className="panel appraisal-section"><div className="section-heading"><h2>{title}</h2>{singular === 'Contribution' && <span className="muted">{items.length} / {limit}</span>}</div>
    {items.length === 0 && <p className="muted">No {itemName} entries.</p>}
    {items.map((item, index) => {
      const removeLabel = `Remove ${itemName} ${index + 1}`;
      return <fieldset className="narrative-item" key={index}><legend>{singular} {index + 1}</legend>
        {fields.map(({key, suffix, label, rows}) => {
          const id = `${singular}-${index}-${suffix}`;
          const status = narrativeStatus(item);
          const missing = status === key || (isGoal && status === 'empty');
          const error = fieldErrors[`${isGoal ? 'goals' : 'contributions'}.${index}.${key}`] ||
            (showErrors && missing ? key === 'employee_narrative'
              ? 'Enter an achievement description or NA.'
              : isGoal ? 'Enter a responsibility / goal description.' : 'Enter a contribution area.' : '');
          const invalid = Boolean(error);
          return <div key={key}>
            <label htmlFor={id}>{label}</label>
            {invalid && <small id={`${id}-error`} className="appraisal-field-error">{error}</small>}
            <CountedTextarea id={id} aria-invalid={invalid || undefined} aria-describedby={invalid ? `${id}-error` : undefined} rows={rows} maxLength={limits[key]} disabled={disabled} value={item[key]} onChange={e => update(index,key,e.target.value)} />
          </div>;
        })}
        {!disabled && <button
          className="button narrative-icon-button"
          type="button"
          disabled={isGoal && items.length <= 1}
          aria-label={removeLabel}
          title={removeLabel}
          onClick={() => {
            if ((!item.description && !item.employee_narrative) || window.confirm(`${removeLabel} and its text?`)) {
              onChange(items.filter((_, i) => i !== index));
            }
          }}
        >−</button>}
      </fieldset>;
    })}
    {!disabled && items.length < limit && <><button
      className="button narrative-icon-button"
      type="button"
      aria-label={addLabel}
      title={addLabel}
      disabled={hasBlankGoal}
      aria-describedby={hasBlankGoal ? 'blank-goal-hint' : undefined}
      onClick={() => onChange([...items, {description:'',employee_narrative:''}])}
    >+</button>{hasBlankGoal && <small id="blank-goal-hint" className="muted"> Start filling the blank goal before adding another.</small>}</>}
  </section>;
}
