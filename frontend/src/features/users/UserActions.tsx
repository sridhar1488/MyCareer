import { useState } from 'react';
import type { FormEvent } from 'react';
import type { components } from '../../api/schema';
import { api } from '../../api/client';
import { Feedback } from '../../components/Feedback';
import { ManagerPicker } from './ManagerPicker';

type Row = components['schemas']['DirectoryUser'];
export function UserActions({ user, mode, ownId, onClose, onSaved }: { user: Row; mode: string; ownId: string; onClose: () => void; onSaved: () => void }) {
  const isOwnSuperAdmin = user.id === ownId && user.roles.includes('SUPER_ADMIN');
  const [link,setLink]=useState<{setup_url:string;expires_at:string;email_status:'queued'|'test_only'|'disabled'}|null>(null);
  const [copied,setCopied]=useState(false);
  const [role, setRole] = useState(user.roles.includes('MANAGER') ? 'MANAGER' : user.roles.includes('SUPER_ADMIN') ? 'SUPER_ADMIN' : 'EMPLOYEE');
  const [superAdmin,setSuperAdmin] = useState(user.roles.includes('MANAGER') && user.roles.includes('SUPER_ADMIN'));
  const requestedRoles = role === 'SUPER_ADMIN' ? ['SUPER_ADMIN'] : [role, ...(superAdmin ? ['SUPER_ADMIN'] : [])];
  const roleUnchanged = requestedRoles.length === user.roles.length && requestedRoles.every(value => user.roles.includes(value));
  const [manager, setManager] = useState(user.manager_id ?? ''); const [managerName, setManagerName] = useState(user.manager_name ?? '');
  const [password, setPassword] = useState(''); const [error, setError] = useState(''); const [busy, setBusy] = useState(false);
  const titles: Record<string, string> = { setup: 'Create private setup link', role: 'Change account role', manager: 'Assign reporting manager', reset: 'Reset temporary password', activate: 'Activate account', deactivate: 'Deactivate account' };
  async function submit(event: FormEvent) {
    event.preventDefault(); setError(''); setBusy(true);
    try {
      const base = `/admin/users/${user.id}`; const version = { expected_version: user.version };
      if(mode==='setup'){setLink(await api(`${base}/setup-link`,'POST',version));return;}
      if (mode === 'role') await api(`${base}/role`, 'PUT', { ...version, role, super_admin:superAdmin });
      else if (mode === 'manager') await api(`${base}/manager`, 'PUT', { ...version, manager_id: manager || null });
      else if (mode === 'reset') await api(`${base}/temporary-password`, 'PUT', { ...version, temporary_password: password });
      else await api(`${base}/${mode}`, 'POST', version);
      setPassword(''); onSaved();
    } catch (error) { setError((error as Error).message); } finally { setBusy(false); }
  }
  return <section className="panel editor"><div className="section-heading"><h2>{titles[mode]} · {user.full_name}</h2><button className="button small" onClick={onClose} disabled={busy}>Cancel</button></div>
    {mode === 'setup' && !link && <p className="muted">Creates a new one-time link valid for seven days. If live email is enabled, MyCareer emails it to this employee; otherwise you can copy it below.</p>}
    {link && <div>{link.email_status === 'queued' && <Feedback success message={`Setup email queued to ${user.email}.`} />}{link.email_status === 'test_only' && <Feedback message="Mail is in test mode: only a test notification was queued, without the working link. Share the link below privately after testing." />}{link.email_status === 'disabled' && <Feedback message="Email notifications are disabled. Share the link below privately." />}<p>This one-time link for {user.full_name} expires {link.expires_at} UTC and is shown once.</p><input readOnly aria-label="Private setup link" value={link.setup_url} onFocus={e=>e.target.select()}/><button className="button" onClick={() => navigator.clipboard.writeText(link.setup_url).then(() => setCopied(true)).catch(() => setCopied(false))}>{copied ? 'Copied' : 'Copy setup link'}</button><button className="button" onClick={onSaved}>Done</button></div>}
    {!link && <>{error && <Feedback message={error} />}<form onSubmit={submit} aria-busy={busy}>
      {mode === 'role' && <>
        <label htmlFor="new-role">Role</label>
        <select id="new-role" value={role} onChange={e => { const next=e.target.value; setRole(next); setSuperAdmin(next === 'MANAGER' && isOwnSuperAdmin); }}>
          <option value="EMPLOYEE" disabled={isOwnSuperAdmin}>Employee</option>
          <option value="MANAGER">Manager</option>
          <option value="SUPER_ADMIN" disabled={isOwnSuperAdmin}>HR / Super Admin</option>
        </select>
        {role === 'MANAGER' && <>
          <label className="choice"><input type="checkbox" checked={superAdmin} disabled={isOwnSuperAdmin} onChange={e => setSuperAdmin(e.target.checked)} />Additional HR / Super Admin access</label>
          <p className="muted">{isOwnSuperAdmin ? 'Your Super Admin access will be preserved while adding the Manager role.' : 'Use this combination when an HR administrator also manages employees.'}</p>
        </>}
        <p className="muted">Employee accounts cannot have Super Admin access. Changing a role signs this user out; their appraisal history remains available.</p>
      </>}
      {mode === 'manager' && <ManagerPicker value={manager} label={managerName} excludeId={user.id} onChange={(id, name) => { setManager(id); setManagerName(name); }} />}
      {mode === 'reset' && <><label htmlFor="reset-password">New temporary password</label><input id="reset-password" type="password" required minLength={8} maxLength={15} autoComplete="new-password" value={password} onChange={e => setPassword(e.target.value)} /><p className="muted">Use 8–15 characters. Existing sessions and reset links will be revoked. Share the temporary password privately; the user must change it at next sign-in.</p></>}
      {mode === 'deactivate' && <p>The employee will be signed out and cannot authenticate until reactivated. Historical records are retained.</p>}
      {mode === 'activate' && <p>This restores account access. Existing appraisal records are retained.</p>}
      <button className="button primary" type="submit" disabled={busy || (user.id === ownId && ['reset', 'deactivate'].includes(mode)) || (mode === 'role' && roleUnchanged)}>{busy ? 'Saving…' : 'Confirm change'}</button>
    </form></>}</section>;
}
