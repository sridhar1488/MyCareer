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
import { HelpPage } from '../features/help/HelpPage';
import { LineIcon } from '../components/LineIcon';
import { MyProfile } from '../features/users/MyProfile';
import { WorkspaceDashboard } from '../features/dashboard/WorkspaceDashboard';
import { navigation, workspaceDestination, workspaceHref, type Page } from './navigation';
import { WorkspaceHeader } from './WorkspaceHeader';

function resetFromLocation() {
  const params = new URLSearchParams(window.location.hash.slice(1));
  const token = params.get('reset') ?? '';
  return token;
}

function homePage(user: User | null): Page {
  return user?.roles.some(role => role === 'MANAGER' || role === 'SUPER_ADMIN') ? 'dashboard' : 'personal';
}

export function App() {
  const [resetToken, setResetToken] = useState(resetFromLocation);
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(!resetToken);
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');
  const [destination, setDestination] = useState(workspaceDestination);
  const [busy, setBusy] = useState(false);
  function authenticated(session: Session) {
    setCsrfToken(session.csrf_token); setUser(session.user); setNotice(''); setError('');
    setDestination(workspaceDestination(homePage(session.user)));
  }
  useEffect(() => {
    function openReset() { const token = resetFromLocation(); if (token) setResetToken(token); }
    window.addEventListener('hashchange', openReset);
    return () => window.removeEventListener('hashchange', openReset);
  }, []);
  useEffect(() => {
    function restoreDestination() {
      const next = workspaceDestination(homePage(user));
      if (next.page === destination.page && next.teamStatus === destination.teamStatus) return;
      if (confirmNavigation()) setDestination(next);
      else window.history.pushState(null, '', workspaceHref(destination.page, destination.teamStatus));
    }
    window.addEventListener('popstate', restoreDestination);
    return () => window.removeEventListener('popstate', restoreDestination);
  }, [destination, user]);
  useEffect(() => {
    if (resetToken) window.history.replaceState(null, '', window.location.pathname + window.location.search);
  }, [resetToken]);
  useEffect(() => {
    if (resetToken) return;
    let active = true;
    api<User>('/auth/me').then(async value => {
      const csrf = await api<{ csrf_token: string }>('/auth/csrf');
      if (active) {
        setCsrfToken(csrf.csrf_token); setUser(value);
        setDestination(workspaceDestination(homePage(value)));
      }
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
    try {
      await api('/auth/logout', 'POST'); setUser(null); setCsrfToken('');
      window.history.replaceState(null, '', workspaceHref());
      setDestination(workspaceDestination());
    }
    catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }
  if (resetToken) return <main className="standalone"><Brand /><PasswordForm resetToken={resetToken} onReset={() => {
    setResetToken(''); setUser(null); setCsrfToken(''); setNotice('Password reset complete. Sign in with your new password.');
  }} /><button className="text-button" onClick={() => setResetToken('')}>Back to sign in</button></main>;
  if (loading) return <main className="standalone"><Brand /><p role="status">Opening your workspace…</p></main>;
  if (!user) return <Login onLogin={authenticated} notice={notice} serviceError={error} />;
  function navigate(next: Page, status = '') {
    if (next === destination.page && status === destination.teamStatus) return true;
    if (!confirmNavigation()) return false;
    window.history.pushState(null, '', workspaceHref(next, status));
    setDestination({ page: next, teamStatus: status });
    window.scrollTo({ top: 0, behavior: 'instant' });
    return true;
  }
  const teamStatus = destination.teamStatus;
  const manager = user.roles.includes('MANAGER');
  const hr = user.roles.includes('SUPER_ADMIN');
  const sidebarItems: Page[] = [];
  const profileItems: Page[] = [];
  if (!user.must_change_password) {
    if (manager || hr) sidebarItems.push('dashboard');
    sidebarItems.push('personal');
    if (manager) sidebarItems.push('team');
    if (hr) sidebarItems.push('calibrations', 'monitor', 'reports', 'forms', 'users', 'cycles');
    sidebarItems.push('help');
    profileItems.push('profile', 'security');
    if (hr) profileItems.push('admin', 'audit');
  }
  const page = [...sidebarItems, ...profileItems].includes(destination.page)
    ? destination.page : user.must_change_password ? 'security' : homePage(user);
  const titles: Partial<Record<Page, string>> = {
    forms: 'Appraisal form builder', reports: 'Final evaluations and reports',
    calibrations: 'HR calibration', monitor: 'HR appraisal monitoring',
  };
  const title = titles[page] ?? navigation[page].label;
  return <div className="workspace"><a className="skip-link" href="#main-content">Skip to main content</a>
    <div className={sidebarItems.length ? 'workspace-layout' : 'workspace-layout workspace-layout-single'}>
      <WorkspaceHeader user={user} page={page} profileItems={profileItems} navigate={navigate} logout={logout} busy={busy} />
      {sidebarItems.length > 0 && <aside className="sidebar">
      <div className="sidebar-brand"><Brand inverse showProduct={false} /></div>
      <p className="sidebar-label">Your Workspace</p>
      <nav aria-label="Main navigation">
        {sidebarItems.map(key => <button key={key} aria-current={page === key ? 'page' : undefined} onClick={() => navigate(key)}>
          <LineIcon path={navigation[key].icon} /><span>{navigation[key].label}</span>
        </button>)}
      </nav>
      <p className="sidebar-tagline"><span>One account.</span>{' '}<span>Room to grow.</span></p>
      </aside>}
    <div className="workspace-body">
      <main id="main-content" className="workspace-main"><h1>{title}</h1>
        {error && <Feedback message={error} />}
        {notice && <Feedback message={notice} success />}
        {user.must_change_password || page === 'security' ? <PasswordForm required={user.must_change_password} onChanged={session => {
          if (destination.page === 'security') window.history.replaceState(null, '', workspaceHref());
          authenticated(session); setNotice('Password changed. Other sessions have been signed out.');
        }} />
          : page === 'help' ? <HelpPage />
          : page === 'profile' ? <MyProfile user={user} onChange={updated => setUser(current => current?.id === updated.id ? updated : current)} />
          : page === 'dashboard' && (manager || hr) ? <WorkspaceDashboard name={user.full_name} manager={manager} hr={hr} navigate={navigate} />
          : page === 'admin' && hr ? <AccountOverview />
          : page === 'team' && manager ? <TeamAppraisals key={teamStatus} initialStatus={teamStatus} />
          : page === 'forms' && hr ? <FormBuilder />
          : page === 'reports' && hr ? <FinalReports />
          : page === 'monitor' && hr ? <HrMonitor />
          : page === 'calibrations' && hr ? <Calibrations />
          : page === 'users' && hr ? <UserDirectory ownId={user.id} />
          : page === 'cycles' && hr ? <Cycles />
          : page === 'audit' && hr ? <AuditLog /> : <MyAppraisals welcomeName={manager || hr ? undefined : user.full_name} />}
      </main>
    </div></div></div>;
}
