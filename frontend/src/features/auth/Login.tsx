import { useState } from 'react';
import type { FormEvent } from 'react';
import { api, type Session } from '../../api/client';
import { Brand } from '../../components/Brand';
import { Feedback } from '../../components/Feedback';

export function Login({ onLogin, notice = '', serviceError = '' }: {
  onLogin: (session: Session) => void; notice?: string; serviceError?: string;
}) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [help, setHelp] = useState(false);
  const [message, setMessage] = useState('');
  async function submit(event: FormEvent) {
    event.preventDefault(); setError(''); setMessage(''); setBusy(true);
    try {
      if (help) {
        const response = await api<{ message: string }>('/auth/forgot-password', 'POST', { email });
        setMessage(response.message);
      } else {
        const session = await api<Session>('/auth/login', 'POST', { email, password });
        setPassword(''); onLogin(session);
      }
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }
  return <div className="login-page">
    <aside className="login-story"><Brand inverse />
      <div className="story-copy"><p className="eyebrow">GROWTH WITH PURPOSE</p>
        <h1>Every contribution.<br />A step forward.</h1>
        <p>A space to reflect on your achievements, connect with your manager, and shape what comes next.</p>
        <div className="story-rule" /><p className="story-caption">Your performance. Your development. Our shared progress.</p>
      </div>
      <p className="story-footer">MedImpact International · People &amp; performance</p>
    </aside>
    <main className="login-main" id="main-content"><div className="login-form-wrap">
      <div className="mobile-brand"><Brand /></div>
      <p className="eyebrow">MYCAREER</p>
      <h2>{help ? 'Reset your password' : 'Welcome back'}</h2>
      <p className="muted">{help ? 'Enter your registered work email to receive a password reset link.' : 'Sign in to your performance workspace.'}</p>
      {notice && <Feedback message={notice} success />}
      {(error || serviceError) && <Feedback message={error || serviceError} />}{message && <Feedback message={message} success />}
      <form onSubmit={submit} aria-busy={busy}>
        <label htmlFor="email">Work email</label>
        <input id="email" name="email" type="email" autoComplete="username" required maxLength={254}
          value={email} onChange={e => setEmail(e.target.value)} placeholder="you@company.com" />
        {!help && <><label htmlFor="password">Password</label>
          <div className="password-input-wrap">
            <input id="password" name="password" type={showPassword ? 'text' : 'password'} autoComplete="current-password" required maxLength={128}
              value={password} onChange={e => setPassword(e.target.value)} />
            <button className="password-visibility" type="button" aria-label={showPassword ? 'Hide password' : 'Show password'}
              aria-pressed={showPassword} onClick={() => setShowPassword(value => !value)}>
              {showPassword ? <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 3l18 18M10.6 10.6a2 2 0 002.8 2.8M9.9 5.2A10.8 10.8 0 0112 5c5.2 0 8.8 5.4 9.5 6.5a1 1 0 010 1 17 17 0 01-3.1 3.7M6.2 6.2A17.4 17.4 0 002.5 11.5a1 1 0 000 1C3.2 13.6 6.8 19 12 19c1.2 0 2.3-.3 3.3-.8" /></svg>
                : <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12z" /><circle cx="12" cy="12" r="3" /></svg>}
            </button>
          </div></>}
        <button className="button primary full-width" type="submit" disabled={busy}>{busy ? 'Please wait…' : help ? 'Send reset link' : 'Sign in'}<span aria-hidden="true"> →</span></button>
      </form>
      <button className="text-button" type="button" onClick={() => { setHelp(!help); setError(''); setMessage(''); setPassword(''); }}>
        {help ? 'Back to sign in' : 'Forgot your password?'}</button>
      <div className="access-note"><span aria-hidden="true">◈</span><p>Use your registered organization account. If your account is not registered or you need help accessing it, contact your administrator.</p></div>
    </div><footer>MyCareer <span>Make progress, together.</span></footer></main>
  </div>;
}
