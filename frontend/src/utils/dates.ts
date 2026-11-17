const dateTimeFormat = new Intl.DateTimeFormat('en-GB', {
  day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit',
  hourCycle: 'h23', timeZone: 'Asia/Kolkata',
});

const istOffset = '+05:30';
const istOffsetMs = 330 * 60_000;
const hasOffset = /(?:Z|[+-]\d\d:\d\d)$/i;

function parseInstant(value: string) {
  return new Date(hasOffset.test(value) ? value : `${value}Z`);
}

export function localDateTime(value: string | null) {
  if (!value) return '—';
  const date = parseInstant(value);
  return Number.isNaN(date.getTime()) ? '—' : `${dateTimeFormat.format(date)} IST`;
}

export function dateTimeInput(value?: string | null) {
  if (!value) return '';
  const date = parseInstant(value);
  return Number.isNaN(date.getTime()) ? '' : new Date(date.getTime() + istOffsetMs).toISOString().slice(0, 16);
}

export function deadlineFromInput(value: string, existing?: string | null) {
  // The editor shows minutes. An unchanged value keeps its original precision.
  if (existing && value === dateTimeInput(existing)) return hasOffset.test(existing) ? existing : `${existing}Z`;
  return `${value}${istOffset}`;
}

const calendarDateFormat = new Intl.DateTimeFormat('en-GB', {
  day: '2-digit', month: 'short', year: 'numeric',
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
