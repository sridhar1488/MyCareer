import type { components } from '../../api/schema';

type Item = components['schemas']['ItemInput'];
export function NarrativeItems({ title, singular, items, limit, disabled, onChange }: { title: string; singular: string; items: Item[]; limit: number; disabled: boolean; onChange: (items: Item[]) => void }) {
  function update(index: number, key: keyof Item, value: string) { onChange(items.map((item,i) => i === index ? { ...item, [key]: value } : item)); }
  return <section className="panel appraisal-section"><div className="section-heading"><h2>{title}</h2><span className="muted">{items.length} / {limit}</span></div>
    {items.length === 0 && <p className="muted">No {singular.toLowerCase()} entries.</p>}
    {items.map((item,index) => <fieldset className="narrative-item" key={index}><legend>{singular} {index+1}</legend>
      <label htmlFor={`${singular}-${index}-description`}>{singular === 'Goal' ? 'Responsibility / goal description' : 'Contribution area'}</label><textarea id={`${singular}-${index}-description`} rows={3} maxLength={5000} disabled={disabled} value={item.description} onChange={e => update(index,'description',e.target.value)} />
      <label htmlFor={`${singular}-${index}-narrative`}>Achievements and self-assessment</label><textarea id={`${singular}-${index}-narrative`} rows={5} maxLength={10000} disabled={disabled} value={item.employee_narrative} onChange={e => update(index,'employee_narrative',e.target.value)} />
      {!disabled && <button className="text-button" type="button" onClick={() => { if ((!item.description && !item.employee_narrative) || window.confirm(`Remove ${singular.toLowerCase()} ${index+1} and its text?`)) onChange(items.filter((_,i) => i !== index)); }}>Remove {singular.toLowerCase()} {index+1}</button>}
    </fieldset>)}
    {!disabled && items.length < limit && <button className="button" type="button" onClick={() => onChange([...items, {description:'',employee_narrative:''}])}>Add {singular.toLowerCase()}</button>}
  </section>;
}
