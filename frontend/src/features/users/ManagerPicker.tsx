import { useState } from 'react';
import type { components } from '../../api/schema';
import { useApi } from '../../api/useApi';
import { Pagination } from '../../components/Pagination';

type Page = components['schemas']['DirectoryPage'];
export function ManagerPicker({ value, label, onChange, excludeId }: { value: string; label: string; onChange: (id: string, name: string) => void; excludeId?: string }) {
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const { data, error } = useApi<Page>(`/admin/users?role=MANAGER&active=true&page=${page}&page_size=10&q=${encodeURIComponent(search)}`);
  return <fieldset className="picker"><legend>Reporting manager</legend><p className="muted">Selected: {label || 'Not assigned'}</p>
    <label htmlFor="manager-search">Find a manager</label><input id="manager-search" value={search} onChange={e => { setSearch(e.target.value); setPage(1); }} placeholder="Name, employee ID or email" />
    {error && <p role="alert">{error}</p>}
    <div className="picker-list">{data?.items.filter(u => u.id !== excludeId).map(u => <label key={u.id} className="choice"><input type="radio" name="manager-selection" value={u.id} checked={value === u.id} onChange={() => onChange(u.id, u.full_name)} />{u.full_name} <small>{u.employee_id}</small></label>)}</div>
    {data && <Pagination page={page} total={data.total} size={10} onPage={setPage} />}
    <button type="button" className="text-button" onClick={() => onChange('', '')}>Clear assignment</button>
  </fieldset>;
}
