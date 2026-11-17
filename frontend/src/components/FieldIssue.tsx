export function invalidField(id: string, error?: string) {
  return error ? {'aria-invalid': true as const, 'aria-describedby': `${id}-error`} : {};
}

export function FieldIssue({id, error}: {id: string; error?: string}) {
  return error ? <small id={`${id}-error`} className="appraisal-field-error">{error}</small> : null;
}
