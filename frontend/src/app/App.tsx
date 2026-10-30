import { useEffect, useState } from 'react';
import { api, ApiError, setCsrfToken, type Session, type User } from '../api/client';
import { Brand } from '../components/Brand';
import { Feedback } from '../components/Feedback';
import { Login } from '../features/auth/Login';
import { PasswordForm } from '../features/auth/PasswordForm';
import { AccountOverview } from '../features/users/AccountOverview';
import { UserDirectory } from '../features/users/UserDirectory';
import { AuditLog } from '../features/users/AuditLog';
import { Cycles } from '../features/hr/Cycles';
import { MyAppraisals } from '../features/appraisals/MyAppraisals';
import { confirmNavigation } from './unsaved';
import { TeamAppraisals } from '../features/reviews/TeamAppraisals';
import {FormBuilder} from '../features/forms/FormBuilder';
import {FinalReports} from '../features/hr/FinalReports';
import { HrMonitor } from '../features/hr/HrMonitor';
import { Calibrations } from '../features/hr/Calibrations';

function resetFromLocation() {
  const params = new URLSearchParams(window.location.hash.slice(1));
  const token = params.get('reset') ?? '';
  return token;
}

export function App() {
  const [resetToken, setResetToken] = useState(resetFromLocation);
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(!resetToken);
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');
  const [page, setPage] = useState('personal');
  const [busy, setBusy] = useState(false);
  function authenticated(session: Session) { setCsrfToken(session.csrf_token); setUser(session.user); setNotice(''); setError(''); setPage('personal'); }
  useEffect(() => {
    function openReset() { const token = resetFromLocation(); if (token) setResetToken(token); }
    window.addEventListener('hashchange', openReset);
    return () => window.removeEventListener('hashchange', openReset);
  }, []);
  useEffect(() => {
    if (resetToken) window.history.replaceState(null, '', window.location.pathname + window.location.search);
  }, [resetToken]);
  useEffect(() => {
    if (resetToken) return;
    let active = true;
    api<User>('/auth/me').then(async value => {
      const csrf = await api<{ csrf_token: string }>('/auth/csrf');
      if (active) { setCsrfToken(csrf.csrf_token); setUser(value); }
    }).catch(e => {
      if (!active) return;
      setUser(null); setCsrfToken('');
      if (!(e instanceof ApiError) || e.status !== 401) setError(e.message);
    })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [resetToken]);
  useEffect(() => {
    function expired() { setUser(null); setCsrfToken(''); setNotice('Your session has expired. Please sign in again.'); }
    window.addEventListener('session-expired', expired);
    return () => window.removeEventListener('session-expired', expired);
  }, []);
  async function logout() {
    if (!confirmNavigation()) return;
    setBusy(true); setError('');
    try { await api('/auth/logout', 'POST'); setUser(null); setCsrfToken(''); setPage('personal'); }
    catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }
  if (resetToken) return <main className="standalone"><Brand /><PasswordForm resetToken={resetToken} onReset={() => {
    setResetToken(''); setUser(null); setCsrfToken(''); setNotice('Password reset complete. Sign in with your new password.');
  }} /><button className="text-button" onClick={() => setResetToken('')}>Back to sign in</button></main>;
  if (loading) return <main className="standalone"><Brand /><p role="status">Opening your workspace…</p></main>;
  if (!user) return <>{error && <div className="service-error"><Feedback message={error} /></div>}<Login onLogin={authenticated} notice={notice} /></>;
  function navigate(next: string) { if (next !== page && confirmNavigation()) setPage(next); }
  const title = ({forms:'Appraisal form builder', reports:'Final evaluations and reports', calibrations:'HR calibration', monitor: 'HR appraisal monitoring', team: 'Team appraisals', security: 'Account security', admin: 'Account overview', users: 'User directory', audit: 'Account audit log', cycles: 'Appraisal cycles'} as Record<string,string>)[page] ?? 'My appraisal';
  return <div className="workspace"><a className="skip-link" href="#main-content">Skip to main content</a>
    <aside className="sidebar"><Brand inverse /><p className="nav-label">YOUR WORKSPACE</p><nav aria-label="Main navigation">
      <button aria-current={page === 'personal' ? 'page' : undefined} onClick={() => navigate('personal')}>My appraisal</button>
      {!user.must_change_password && user.roles.includes('MANAGER') && <button aria-current={page === 'team' ? 'page' : undefined} onClick={() => navigate('team')}>Team appraisals</button>}
      {!user.must_change_password && user.roles.includes('SUPER_ADMIN') && <>{[['calibrations','HR approval queue'],['monitor','HR monitoring'],['reports','Final evaluations'],['forms','Appraisal forms'],['users','User directory'],['cycles','Appraisal cycles'],['admin','Account overview'],['audit','Account audit log']].map(([key,label]) => <button key={key} aria-current={page === key ? 'page' : undefined} onClick={() => navigate(key)}>{label}</button>)}</>}
      <button aria-current={page === 'security' ? 'page' : undefined} onClick={() => navigate('security')}>Account security</button>
    </nav><div className="sidebar-bottom"><span className="role-badge">{user.roles.map(r => r.replaceAll('_', ' ')).join(' · ')}</span><p>One account.<br />Room to grow.</p></div></aside>
    <div className="workspace-body"><header className="topbar"><span>Performance &amp; development</span><div><span className="user-name">{user.full_name}</span><button className="button small" onClick={logout} disabled={busy}>{busy ? 'Signing out…' : 'Sign out'}</button></div></header>
      <main id="main-content" className="workspace-main"><p className="eyebrow">MYCAREER</p><h1>{title}</h1>
        {error && <Feedback message={error} />}
        {notice && <Feedback message={notice} success />}
        {user.must_change_password || page === 'security' ? <PasswordForm required={user.must_change_password} onChanged={session => { authenticated(session); setNotice('Password changed. Other sessions have been signed out.'); }} />
          : page === 'admin' && user.roles.includes('SUPER_ADMIN') ? <AccountOverview />
          : page === 'team' && user.roles.includes('MANAGER') ? <TeamAppraisals />
          : page === 'forms' && user.roles.includes('SUPER_ADMIN') ? <FormBuilder />
          : page === 'reports' && user.roles.includes('SUPER_ADMIN') ? <FinalReports />
          : page === 'monitor' && user.roles.includes('SUPER_ADMIN') ? <HrMonitor />
          : page === 'calibrations' && user.roles.includes('SUPER_ADMIN') ? <Calibrations />
          : page === 'users' && user.roles.includes('SUPER_ADMIN') ? <UserDirectory ownId={user.id} />
          : page === 'cycles' && user.roles.includes('SUPER_ADMIN') ? <Cycles />
          : page === 'audit' && user.roles.includes('SUPER_ADMIN') ? <AuditLog /> : <>
            <section className="welcome-panel"><div><span className="eyebrow">YOUR NEXT STEP STARTS HERE</span><h2>Welcome, {user.full_name.split(' ')[0]}.</h2><p>Reflect on your contribution.<br />Build on your progress.</p></div><div className="growth-art" aria-hidden="true"><span /><span /><span /><span /></div></section>
            <section className="panel"><div className="section-heading"><h2>Your profile</h2><span className="status-dot">Account active</span></div>
              <dl className="profile-grid">{[['Employee ID', user.employee_id], ['Work email', user.email], ['Department', user.department || 'Not provided'], ['Designation', user.designation || 'Not provided'], ['Country', user.country || 'Not provided']].map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl></section>
            <MyAppraisals />
          </>}
      </main><footer className="workspace-footer"><div className="workspace-footer-content"><span>MyCareer</span><span className="footer-company">MedImpact International</span></div></footer>
    </div></div>;
}
