import { useState } from 'react';
import type { FormEvent } from 'react';
import type { components } from '../../api/schema';
import { api } from '../../api/client';
import { Feedback } from '../../components/Feedback';
import { ManagerPicker } from './ManagerPicker';

type DirectoryUser = components['schemas']['DirectoryUser'];
type Role = components['schemas']['RoleCode'];
export function UserEditor({ user, onClose, onSaved }: { user?: DirectoryUser; onClose: () => void; onSaved: () => void }) {
  const [fields, setFields] = useState({ full_name: user?.full_name ?? '', employee_id: user?.employee_id ?? '', email: user?.email ?? '', department: user?.department ?? '', designation: user?.designation ?? '', country: user?.country ?? '' });
  const [role, setRole] = useState<Role>('EMPLOYEE');
  const [superAdmin,setSuperAdmin] = useState(false);
  const [manager, setManager] = useState(''); const [managerName, setManagerName] = useState('');
  const [password, setPassword] = useState(''); const [error, setError] = useState(''); const [busy, setBusy] = useState(false);
  async function submit(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError('');
    try {
      if (user) await api(`/admin/users/${user.id}`, 'PATCH', { ...fields, expected_version: user.version });
      else await api('/admin/users', 'POST', { ...fields, role, super_admin:superAdmin, manager_id: manager || null, temporary_password: password });
      setPassword(''); onSaved();
    } catch (error) { setError((error as Error).message); } finally { setBusy(false); }
  }
  return <section className="panel editor" aria-labelledby="editor-heading"><div className="section-heading"><h2 id="editor-heading">{user ? 'Edit employee profile' : 'Create employee account'}</h2><button className="button small" onClick={onClose} disabled={busy}>Cancel</button></div>
    {error && <Feedback message={error} />}<form onSubmit={submit} aria-busy={busy}><div className="form-grid">
      {([['full_name', 'Full name', 150], ['employee_id', 'Employee ID', 40], ['email', 'Work email', 254], ['department', 'Department', 100], ['designation', 'Designation', 100], ['country', 'Country', 80]] as const).map(([key, label, max]) => <div key={key}><label htmlFor={`user-${key}`}>{label}</label><input id={`user-${key}`} required maxLength={max} type={key === 'email' ? 'email' : 'text'} value={fields[key]} onChange={e => setFields({ ...fields, [key]: e.target.value })} /></div>)}
    </div>{!user && <><label htmlFor="role">Role</label><select id="role" value={role} onChange={e => setRole(e.target.value as Role)}><option value="EMPLOYEE">Employee</option><option value="MANAGER">Manager</option></select><label className="choice"><input type="checkbox" checked={superAdmin} onChange={e => setSuperAdmin(e.target.checked)} />Additional HR / Super Admin access</label><p className="muted">A Manager with HR / Super Admin access can review assigned employees and administer the organization using the same account.</p>
      <ManagerPicker value={manager} label={managerName} onChange={(id, name) => { setManager(id); setManagerName(name); }} />
      <label htmlFor="temporary-password">Temporary password</label><input id="temporary-password" type="password" required minLength={8} maxLength={15} autoComplete="new-password" value={password} onChange={e => setPassword(e.target.value)} /><p className="muted">Use 8–15 characters. Share privately with the employee; a password change is required on first sign-in.</p></>}
      <button className="button primary" disabled={busy} type="submit">{busy ? 'Saving…' : user ? 'Save profile' : 'Create account'}</button></form></section>;
}
