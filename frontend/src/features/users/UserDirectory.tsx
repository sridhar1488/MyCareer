import { useState } from 'react';
import type { components } from '../../api/schema';
import { useApi } from '../../api/useApi';
import { Feedback } from '../../components/Feedback';
import { Pagination } from '../../components/Pagination';
import { localDateTime } from '../../utils/dates';
import { UserEditor } from './UserEditor';
import {BulkImport} from './BulkImport';
import { UserActions } from './UserActions';

type Row = components['schemas']['DirectoryUser']; type Page = components['schemas']['DirectoryPage'];
export function UserDirectory({ ownId }: { ownId: string }) {
  const [importing,setImporting]=useState(false);
  const [q, setQ] = useState(''); const [role, setRole] = useState(''); const [active, setActive] = useState('');
  const [department, setDepartment] = useState(''); const [sort, setSort] = useState('full_name'); const [page, setPage] = useState(1); const [revision, setRevision] = useState(0);
  const [editor, setEditor] = useState<{ mode: string; user?: Row } | null>(null); const [message, setMessage] = useState('');
  const params = new URLSearchParams({ q, sort, page: String(page), ...(role ? { role } : {}), ...(active ? { active } : {}), ...(department ? { department } : {}) });
  const { data, error, loading } = useApi<Page>(`/admin/users?${params}`, revision);
  function saved() { setMessage(editor?.mode === 'create' ? 'Account created. The employee must change the temporary password at first sign-in.' : 'Account changes saved.'); setEditor(null); setRevision(revision + 1); }
  if(importing)return <BulkImport onClose={()=>{setImporting(false);setRevision(revision+1);}}/>;
  if (editor) return editor.mode === 'create' || editor.mode === 'edit' ? <UserEditor key={editor.user?.id ?? 'new'} user={editor.user} onClose={() => setEditor(null)} onSaved={saved} /> : <UserActions key={`${editor.user!.id}-${editor.mode}`} user={editor.user!} mode={editor.mode} ownId={ownId} onClose={() => setEditor(null)} onSaved={saved} />;
  return <>{message && <Feedback message={message} success />}<section className="panel"><div className="section-heading"><div><h2>Employee accounts</h2><p className="muted">Manage access, profiles and reporting relationships.</p></div><button className="button" onClick={()=>setImporting(true)}>Import users from Excel</button><button className="button primary" onClick={() => { setMessage(''); setEditor({ mode: 'create' }); }}>Create user</button></div>
    <div className="filters"><div><label htmlFor="directory-search">Search users</label><input id="directory-search" value={q} onChange={e => { setQ(e.target.value); setPage(1); }} placeholder="Name, ID or email" /></div>
      <div><label htmlFor="filter-role">Role</label><select id="filter-role" value={role} onChange={e => { setRole(e.target.value); setPage(1); }}><option value="">All roles</option>{['EMPLOYEE', 'MANAGER', 'SUPER_ADMIN'].map(r => <option key={r}>{r}</option>)}</select></div>
      <div><label htmlFor="filter-status">Account status</label><select id="filter-status" value={active} onChange={e => { setActive(e.target.value); setPage(1); }}><option value="">All statuses</option><option value="true">Active</option><option value="false">Inactive</option></select></div>
      <div><label htmlFor="filter-department">Department</label><input id="filter-department" value={department} onChange={e => { setDepartment(e.target.value); setPage(1); }} /></div>
      <div><label htmlFor="directory-sort">Sort by</label><select id="directory-sort" value={sort} onChange={e => setSort(e.target.value)}>{[['full_name','Name'],['employee_id','Employee ID'],['email','Email'],['department','Department'],['created_at','Created date']].map(([value,label]) => <option key={value} value={value}>{label}</option>)}</select></div></div>
    {loading && <p role="status">Loading users…</p>}{error && <><Feedback message={error} /><button className="button" onClick={() => setRevision(revision + 1)}>Try again</button></>}
    {data && <><div className="table-scroll"><table><thead><tr><th>Employee</th><th>Department / designation</th><th>Role / manager</th><th>Status / dates</th><th>Actions</th></tr></thead><tbody>{data.items.map(u => <tr key={u.id}><td><strong>{u.full_name}</strong><small>{u.employee_id}</small><small>{u.email}</small></td><td>{u.department || '—'}<small>{u.designation || '—'}</small></td><td>{u.roles.join(', ')}<small>{u.manager_name || 'Manager not assigned'}</small></td><td><span className={`status ${u.active ? 'active' : ''}`}>{u.active ? 'Active' : 'Inactive'}</span><small>Created {localDateTime(u.created_at)}</small><small>Last login {localDateTime(u.last_login_at)}</small></td><td><div className="row-actions">{[['edit','Edit profile'],['manager','Assign manager'],['role','Change role'],['reset','Reset password'],['setup','Create setup link'],[u.active ? 'deactivate' : 'activate',u.active ? 'Deactivate' : 'Activate']].map(([mode,label]) => <button key={mode} className="text-button" disabled={u.id === ownId && ['role','reset','setup','deactivate'].includes(mode)} onClick={() => setEditor({mode,user:u})}>{label}<span className="sr-only"> for {u.full_name}</span></button>)}</div></td></tr>)}</tbody></table></div>{data.total === 0 && <p>No users match these filters.</p>}<Pagination page={page} total={data.total} onPage={setPage} /></>}
  </section></>;
}
