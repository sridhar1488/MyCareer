import { useState } from 'react';
import type { FormEvent } from 'react';
import { api, type Session } from '../../api/client';
import { Feedback } from '../../components/Feedback';

type Props = { required?: boolean; resetToken?: string; onChanged?: (session: Session) => void; onReset?: () => void };
export function PasswordForm({ required = false, resetToken, onChanged, onReset }: Props) {
  const [current, setCurrent] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  async function submit(event: FormEvent) {
    event.preventDefault(); setError(''); setSuccess('');
    if (password !== confirm) { setError('Your new passwords do not match.'); return; }
    if (password.length < 8 || password.length > 15) { setError('Use 8–15 characters for your new password.'); return; }
    setBusy(true);
    try {
      if (resetToken) {
        await api('/auth/complete-password-setup', 'POST', { token: resetToken, new_password: password });
        setCurrent(''); setPassword(''); setConfirm(''); onReset?.();
      } else {
        const session = await api<Session>('/auth/change-password', 'POST', { current_password: current, new_password: password });
        setCurrent(''); setPassword(''); setConfirm('');
        setSuccess('Your password has been changed. Other sessions have been signed out.'); onChanged?.(session);
      }
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }
  return <section className="panel password-panel" aria-labelledby="password-heading">
    <p className="eyebrow">ACCOUNT SECURITY</p><h2 id="password-heading">{resetToken ? 'Set a new password' : required ? 'Choose your own password' : 'Change password'}</h2>
    <p className="muted">{required ? 'Change your temporary password before continuing.' : 'Use a unique password of 8–15 characters.'}</p>
    {error && <Feedback message={error} />}{success && <Feedback message={success} success />}
    <form onSubmit={submit} aria-busy={busy}>
      {!resetToken && <><label htmlFor="current">Current password</label><input id="current" type="password" required autoComplete="current-password" maxLength={128} value={current} onChange={e => setCurrent(e.target.value)} /></>}
      <label htmlFor="new-password">New password</label><input id="new-password" type="password" required autoComplete="new-password" minLength={8} maxLength={15} aria-describedby="password-hint" value={password} onChange={e => setPassword(e.target.value)} />
      <small className="muted" id="password-hint">Use 8–15 characters. Spaces and all character types are supported.</small>
      <label htmlFor="confirm">Confirm new password</label><input id="confirm" type="password" required autoComplete="new-password" minLength={8} maxLength={15} value={confirm} onChange={e => setConfirm(e.target.value)} />
      <button className="button primary" disabled={busy} type="submit">{busy ? 'Saving…' : 'Save new password'}</button>
    </form>
  </section>;
}
