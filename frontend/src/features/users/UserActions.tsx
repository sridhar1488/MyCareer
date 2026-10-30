import { useState } from 'react';
import type { FormEvent } from 'react';
import type { components } from '../../api/schema';
import { api } from '../../api/client';
import { Feedback } from '../../components/Feedback';
import { ManagerPicker } from './ManagerPicker';

type Row = components['schemas']['DirectoryUser'];
export function UserActions({ user, mode, ownId, onClose, onSaved }: { user: Row; mode: string; ownId: string; onClose: () => void; onSaved: () => void }) {
  const [link,setLink]=useState<{setup_url:string;expires_at:string}|null>(null);
  const [role, setRole] = useState(user.roles.includes('MANAGER') ? 'MANAGER' : 'EMPLOYEE');
  const [superAdmin,setSuperAdmin] = useState(user.roles.includes('SUPER_ADMIN'));
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
    {link && <div><p>Share privately with {user.full_name}. This one-time link expires {link.expires_at} UTC and is shown once.</p><input readOnly aria-label="Private setup link" value={link.setup_url} onFocus={e=>e.target.select()}/><button className="button" onClick={onSaved}>Done</button></div>}
    {!link && <>{error && <Feedback message={error} />}<form onSubmit={submit} aria-busy={busy}>
      {mode === 'role' && <><label htmlFor="new-role">Role</label><select id="new-role" value={role} onChange={e => setRole(e.target.value)}>{['EMPLOYEE', 'MANAGER'].map(r => <option key={r} value={r}>{r === 'SUPER_ADMIN' ? 'HR / Super Admin' : r}</option>)}</select><label className="choice"><input type="checkbox" checked={superAdmin} onChange={e => setSuperAdmin(e.target.checked)} />Additional HR / Super Admin access</label><p className="muted">Changing a role signs this user out. Their personal appraisal remains their own.</p></>}
      {mode === 'manager' && <ManagerPicker value={manager} label={managerName} excludeId={user.id} onChange={(id, name) => { setManager(id); setManagerName(name); }} />}
      {mode === 'reset' && <><label htmlFor="reset-password">New temporary password</label><input id="reset-password" type="password" required minLength={8} maxLength={15} autoComplete="new-password" value={password} onChange={e => setPassword(e.target.value)} /><p className="muted">Use 8–15 characters. Existing sessions and reset links will be revoked. Share the temporary password privately; the user must change it at next sign-in.</p></>}
      {mode === 'deactivate' && <p>The employee will be signed out and cannot authenticate until reactivated. Historical records are retained.</p>}
      {mode === 'activate' && <p>This restores account access. Existing appraisal records are retained.</p>}
      <button className="button primary" type="submit" disabled={busy || (user.id === ownId && ['role', 'reset', 'deactivate'].includes(mode))}>{busy ? 'Saving…' : 'Confirm change'}</button>
    </form></>}</section>;
}
