import type { ComponentPropsWithoutRef } from 'react';
import { isSingleCharacter } from '../utils/appraisalTextLimits';

type Props = ComponentPropsWithoutRef<'textarea'> & { id: string; maxLength: number; value: string };

export function CountedTextarea({ id, maxLength, value, 'aria-describedby': describedBy, 'aria-invalid': invalid, ...props }: Props) {
  const countId = `${id}-count`;
  const errorId = `${id}-minimum`;
  const tooShort = !props.disabled && isSingleCharacter(value);
  const remaining = maxLength - value.length;

  return <>
    {tooShort && <small id={errorId} className="appraisal-field-error">Enter at least 2 characters. Use NA if it does not apply.</small>}
    <small id={countId} className="character-count muted">
      {remaining >= 0
        ? `${remaining} of ${maxLength} characters remaining`
        : `${-remaining} characters over the ${maxLength}-character limit. Saved text is retained.`}
    </small>
    <textarea {...props} id={id} maxLength={maxLength} value={value}
      aria-invalid={tooShort || invalid}
      aria-describedby={[countId, describedBy, tooShort && errorId].filter(Boolean).join(' ')} />
  </>;
}
