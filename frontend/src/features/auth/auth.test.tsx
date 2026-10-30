import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { Login } from './Login';
import { PasswordForm } from './PasswordForm';

afterEach(() => vi.unstubAllGlobals());

describe('Authentication forms', () => {
  it('sends credentials and displays server errors without exposing the password', async () => {
    const fetch = vi.fn().mockResolvedValue({ ok: false, status: 401, json: async () => ({ error: { code: 'INVALID_CREDENTIALS', message: 'Email or password is incorrect.' } }) });
    vi.stubGlobal('fetch', fetch);
    const user = userEvent.setup();
    render(<Login onLogin={vi.fn()} />);
    await user.type(screen.getByLabelText('Work email'), 'member@example.org');
    await user.type(screen.getByLabelText('Password'), 'a private passphrase');
    await user.click(screen.getByRole('button', { name: 'Sign in' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Email or password is incorrect.');
    expect(screen.getByRole('alert')).not.toHaveTextContent('a private passphrase');
    expect(fetch).toHaveBeenCalledOnce();
  });

  it('provides reset assistance without requesting a password', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, status: 202, json: async () => ({ message: 'Contact your account administrator.' }) }));
    const user = userEvent.setup();
    render(<Login onLogin={vi.fn()} />);
    await user.click(screen.getByRole('button', { name: 'Forgot your password?' }));
    expect(screen.queryByLabelText('Password')).not.toBeInTheDocument();
    await user.type(screen.getByLabelText('Work email'), 'member@example.org');
    await user.click(screen.getByRole('button', { name: 'Request reset assistance' }));
    expect(await screen.findByRole('status')).toHaveTextContent('Contact your account administrator.');
  });

  it('lets the user reveal and hide the sign-in password', async () => {
    const user = userEvent.setup();
    render(<Login onLogin={vi.fn()} />);
    const password = screen.getByLabelText('Password');
    await user.type(password, 'Pass8abc');
    expect(password).toHaveAttribute('type', 'password');
    await user.click(screen.getByRole('button', { name: 'Show password' }));
    expect(password).toHaveAttribute('type', 'text');
    expect(password).toHaveValue('Pass8abc');
    await user.click(screen.getByRole('button', { name: 'Hide password' }));
    expect(password).toHaveAttribute('type', 'password');
  });

  it('prevents mismatched passwords from reaching the API', async () => {
    const fetch = vi.fn(); vi.stubGlobal('fetch', fetch);
    const user = userEvent.setup();
    render(<PasswordForm />);
    await user.type(screen.getByLabelText('Current password'), 'old secret passphrase');
    await user.type(screen.getByLabelText('New password'), 'my new secret passphrase');
    await user.type(screen.getByLabelText('Confirm new password'), 'a different secret passphrase');
    await user.click(screen.getByRole('button', { name: 'Save new password' }));
    expect(screen.getByRole('alert')).toHaveTextContent('do not match');
    expect(fetch).not.toHaveBeenCalled();
  });

  it('reports network failure and permits retry', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('offline')));
    const user = userEvent.setup();
    render(<Login onLogin={vi.fn()} />);
    await user.type(screen.getByLabelText('Work email'), 'member@example.org');
    await user.type(screen.getByLabelText('Password'), 'a private passphrase');
    await user.click(screen.getByRole('button', { name: 'Sign in' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('could not reach the service');
    expect(screen.getByRole('button', { name: 'Sign in' })).toBeEnabled();
  });
});
