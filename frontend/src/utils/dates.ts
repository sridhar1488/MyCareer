export function localDateTime(value: string | null) {
  if (!value) return '—';
  return new Date(/(?:Z|[+-]\d\d:\d\d)$/.test(value) ? value : `${value}Z`).toLocaleString();
}

const calendarDateFormat = new Intl.DateTimeFormat(undefined, {
  dateStyle: 'medium',
  timeZone: 'UTC',
});

export function calendarDate(value: string) {
  return calendarDateFormat.format(new Date(`${value}T00:00:00Z`));
}

export function appraisalPeriod(start: string, end: string) {
  const year = start.slice(0, 4);
  if (start === `${year}-01-01` && end === `${year}-12-31`) return year;
  return `${calendarDate(start)} – ${calendarDate(end)}`;
}
