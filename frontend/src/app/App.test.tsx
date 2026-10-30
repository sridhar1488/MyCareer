import { StrictMode } from 'react';
import { render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { App } from './App';

afterEach(() => { vi.unstubAllGlobals(); window.history.replaceState(null, '', '/'); });

it('keeps a reset token through StrictMode initialization while immediately removing it from history', () => {
  const fetch = vi.fn(); vi.stubGlobal('fetch', fetch);
  window.history.replaceState(null, '', '/#reset=test-only-opaque-reset-token-with-48-characters');
  render(<StrictMode><App /></StrictMode>);
  expect(screen.getByRole('heading', { name: 'Set a new password' })).toBeInTheDocument();
  expect(window.location.hash).toBe('');
  expect(fetch).not.toHaveBeenCalled();
});

it('shows the sign-in form after an expired session without displaying an internal error', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 401,
    json: async () => ({ error: { code: 'SESSION_EXPIRED', message: 'Please sign in again.' } }) }));
  render(<App />);
  expect(await screen.findByRole('heading', { name: 'Welcome back' })).toBeVisible();
  expect(screen.queryByRole('alert')).not.toBeInTheDocument();
});
