import { expect, test } from 'vitest';
import { calendarDate, dateTimeInput, deadlineFromInput, localDateTime } from './dates';

test('displays the same IST day boundary from UTC and already offset timestamps', () => {
  expect(localDateTime('2026-11-29T18:30:00Z')).toBe('30 Nov 2026, 00:00 IST');
  expect(localDateTime('2026-11-30T00:00:00+05:30')).toBe('30 Nov 2026, 00:00 IST');
  expect(calendarDate('2026-11-29')).toBe('29 Nov 2026');
});

test('interprets edited deadlines in IST and preserves the precision of an unchanged deadline', () => {
  const saved = '2026-11-29T18:30:12.123456';
  expect(dateTimeInput(saved)).toBe('2026-11-30T00:00');
  expect(deadlineFromInput('2026-11-30T00:00', saved)).toBe(`${saved}Z`);
  expect(deadlineFromInput('2026-11-30T23:59', saved)).toBe('2026-11-30T23:59+05:30');
});
