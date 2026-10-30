export function localDateTime(value: string | null) {
  if (!value) return '—';
  return new Date(/(?:Z|[+-]\d\d:\d\d)$/.test(value) ? value : `${value}Z`).toLocaleString();
}
