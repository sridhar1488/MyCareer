import { useEffect, useState } from 'react';
import { api, type AccountSummary } from '../../api/client';
import { Feedback } from '../../components/Feedback';

export function AccountOverview() {
  const [data, setData] = useState<AccountSummary | null>(null);
  const [error, setError] = useState('');
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let active = true;
    api<AccountSummary>('/admin/summary').then(value => { if (active) { setData(value); setError(''); } })
      .catch(e => { if (active) setError(e.message); });
    return () => { active = false; };
  }, [attempt]);
  if (error) return <><Feedback message={error} /><button className="button" onClick={() => setAttempt(attempt + 1)}>Try again</button></>;
  if (!data) return <p role="status">Loading account overview…</p>;
  return <><div className="stat-grid"><section className="panel stat"><p>Total accounts</p><strong>{data.total_accounts}</strong></section>
    <section className="panel stat"><p>Active accounts</p><strong>{data.active_accounts}</strong></section>
    <section className="panel stat"><p>Inactive accounts</p><strong>{data.total_accounts - data.active_accounts}</strong></section></div>
    <section className="panel"><h2>Roles across your organization</h2><dl className="profile-grid">{Object.entries(data.role_counts).map(([role, count]) => <div key={role}><dt>{role.replaceAll('_', ' ')}</dt><dd>{count}</dd></div>)}</dl></section></>;
}
