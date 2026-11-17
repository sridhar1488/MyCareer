import type { components } from '../../api/schema';
import { CountedTextarea } from '../../components/CountedTextarea';
import { FieldIssue, invalidField } from '../../components/FieldIssue';
import { appraisalResponseLimit } from '../../utils/appraisalTextLimits';

type Rating = components['schemas']['RatingInput'];
const labels = ['Unsatisfactory','Inconsistent','Effective','Highly Effective','Exceptional'];

export function RatingFields({id, label, value, disabled, onChange, allowNA = false,
  commentReadOnly = false, errors = {}}: {
  id: string; label: string; value: Rating; disabled: boolean; onChange: (value: Rating) => void;
  allowNA?: boolean; commentReadOnly?: boolean; errors?: Record<string, string>;
}) {
  const reasonId = `${id}-reason`;
  const ratingId = `${id}-rating`;
  const commentId = `${id}-comment`;
  return <fieldset>
    <legend>{label}</legend>
    {allowNA && <>
      <label className="choice"><input type="checkbox" disabled={disabled} checked={value.not_applicable ?? false}
        onChange={event => onChange({...value, not_applicable: event.target.checked, rating: null, applicability_reason: ''})} />
        Leadership is not applicable
      </label>
      {value.not_applicable && <>
        <label htmlFor={reasonId}>Leadership applicability reason</label>
        <FieldIssue id={reasonId} error={errors[reasonId]} />
        <CountedTextarea id={reasonId} {...invalidField(reasonId, errors[reasonId])}
          disabled={disabled} maxLength={appraisalResponseLimit} rows={3} value={value.applicability_reason ?? ''}
          onChange={event => onChange({...value, applicability_reason: event.target.value})} />
      </>}
    </>}
    <label htmlFor={ratingId}>Rating</label>
    <FieldIssue id={ratingId} error={errors[ratingId]} />
    <select id={ratingId} {...invalidField(ratingId, errors[ratingId])}
      disabled={disabled || value.not_applicable} value={value.rating ?? ''}
      onChange={event => onChange({...value, rating: event.target.value ? Number(event.target.value) : null})}>
      <option value="">Not rated</option>
      {labels.map((text, i) => <option key={i + 1} value={i + 1}>{i + 1} — {text}</option>)}
    </select>
    <label htmlFor={commentId}>Supporting evaluation comment</label>
    <FieldIssue id={commentId} error={errors[commentId]} />
    <CountedTextarea id={commentId} {...invalidField(commentId, errors[commentId])} rows={4}
      maxLength={appraisalResponseLimit} disabled={disabled || commentReadOnly || value.not_applicable}
      value={value.comment ?? ''} onChange={event => onChange({...value, comment: event.target.value})} />
  </fieldset>;
}
