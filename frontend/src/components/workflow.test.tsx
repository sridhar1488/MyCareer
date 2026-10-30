import { fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, test, vi } from 'vitest';
import { Pagination } from './Pagination';
import { confirmNavigation, markUnsaved } from '../app/unsaved';

afterEach(() => { markUnsaved(false); vi.restoreAllMocks(); });

test('picker pagination does not submit its enclosing account or cycle form', () => {
  const submitted = vi.fn((event: React.FormEvent) => event.preventDefault());
  const next = vi.fn();
  render(<form onSubmit={submitted}><Pagination page={1} total={30} onPage={next} /></form>);
  fireEvent.click(screen.getByRole('button', {name:'Next'}));
  expect(next).toHaveBeenCalledWith(2);
  expect(submitted).not.toHaveBeenCalled();
});

test('unsaved assessment blocks navigation until the employee confirms', () => {
  const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false);
  expect(confirmNavigation()).toBe(true);
  expect(confirm).not.toHaveBeenCalled();
  markUnsaved(true);
  expect(confirmNavigation()).toBe(false);
  confirm.mockReturnValue(true);
  expect(confirmNavigation()).toBe(true);
  markUnsaved(false);
  expect(confirmNavigation()).toBe(true);
});
