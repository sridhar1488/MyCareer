import { useState } from 'react';
import type { FormEvent } from 'react';
import type { components } from '../../api/schema';
import { api } from '../../api/client';
import { useApi } from '../../api/useApi';
import { Feedback } from '../../components/Feedback';
import { Pagination } from '../../components/Pagination';

type Cycle = components['schemas']['CycleResponse'];
type ParticipantRole = 'EMPLOYEE' | 'MANAGER';
const participantLimit = 10_000;
function dateInput(value?: string) { if (!value) return ''; const d = new Date(`${value}Z`); return new Date(d.getTime() - d.getTimezoneOffset()*60000).toISOString().slice(0,16); }
export function CycleEditor({ cycle, onCancel, onSaved }: { cycle?: Cycle; onCancel: () => void; onSaved: () => void }) {
  const [formVersion,setFormVersion]=useState(cycle?.form_version_id ?? 'workbook-ye2025-v1');
  const {data:forms}=useApi<components['schemas']['PublishedForm'][]>('/hr/forms/published');
  const [title, setTitle] = useState(cycle?.title ?? ''); const [start, setStart] = useState(cycle?.period_start ?? ''); const [end, setEnd] = useState(cycle?.period_end ?? '');
  const [deadline, setDeadline] = useState(dateInput(cycle?.submission_deadline)); const [minGoals, setMinGoals] = useState(cycle?.min_goals ?? 1); const [late, setLate] = useState(cycle?.allow_late_submission ?? false);
  const [selected, setSelected] = useState(new Set(cycle?.participant_ids ?? [])); const [search, setSearch] = useState(''); const [page, setPage] = useState(1);
  const [error, setError] = useState(''); const [busy, setBusy] = useState(false);
  const [selecting, setSelecting] = useState<ParticipantRole | null>(null);
  const [selectionNotice, setSelectionNotice] = useState('');
  const [selectionError, setSelectionError] = useState('');
  const { data, error: lookupError } = useApi<components['schemas']['ParticipantPage']>(`/cycles/participant-options?page=${page}&page_size=25&q=${encodeURIComponent(search)}`);
  async function selectRole(role: ParticipantRole) {
    setSelecting(role); setSelectionNotice(''); setSelectionError('');
    try {
      const result = await api<components['schemas']['BulkParticipantOptions']>(`/cycles/participant-options/bulk?role=${role}`);
      const next = new Set([...selected, ...result.participant_ids]);
      if (next.size > participantLimit) {
        setSelectionError(`A cycle can include up to ${participantLimit.toLocaleString()} participants. Clear or reduce your current selection before adding this group.`);
        return;
      }
      setSelected(next);
      const group = role === 'EMPLOYEE' ? 'employee' : 'manager';
      const count = result.participant_ids.length;
      const summary = count ? `Selected ${count.toLocaleString()} eligible ${group}${count === 1 ? '' : 's'}.` : `No eligible ${group}s found.`;
      const skipped = result.skipped ? ` Skipped ${result.skipped.toLocaleString()} without a valid reporting manager.` : '';
      setSelectionNotice(summary + skipped);
    } catch (e) { setSelectionError((e as Error).message); }
    finally { setSelecting(null); }
  }
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (busy || selecting) return;
    setError(''); if (!selected.size) { setError('Choose at least one participant.'); return; }
    setBusy(true);
    try {
      const body = { form_version_id:formVersion, title, period_start: start, period_end: end, submission_deadline: new Date(deadline).toISOString(), min_goals: minGoals, allow_late_submission: late, participant_ids: [...selected], ...(cycle ? { expected_version: cycle.version } : {}) };
      await api(cycle ? `/cycles/${cycle.id}` : '/cycles', cycle ? 'PATCH' : 'POST', body); onSaved();
    } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }
  return <section className="panel editor"><div className="section-heading"><h2>{cycle ? 'Edit draft cycle' : 'Create appraisal cycle'}</h2><button className="button" onClick={onCancel} disabled={busy || selecting !== null}>Cancel</button></div>{error && <Feedback message={error} />}
    <form onSubmit={submit} aria-busy={busy}><label htmlFor="cycle-title">Cycle title</label><input id="cycle-title" required maxLength={150} value={title} onChange={e => setTitle(e.target.value)} />
      <div className="form-grid"><div><label htmlFor="period-start">Appraisal period start</label><input id="period-start" type="date" required value={start} onChange={e => setStart(e.target.value)} /></div><div><label htmlFor="period-end">Appraisal period end</label><input id="period-end" type="date" required min={start} value={end} onChange={e => setEnd(e.target.value)} /></div></div>
      <label htmlFor="cycle-form">Published appraisal form</label><select id="cycle-form" value={formVersion} onChange={e=>setFormVersion(e.target.value)}>{forms?.map(f=><option key={f.id} value={f.id}>{f.name}</option>)}</select>
      <label htmlFor="deadline">Employee submission deadline</label><input id="deadline" type="datetime-local" required value={deadline} onChange={e => setDeadline(e.target.value)} /><p className="muted">Time zone: {Intl.DateTimeFormat().resolvedOptions().timeZone}. Stored as UTC.</p>
      <label htmlFor="minimum-goals">Minimum completed goals required for submission</label><select id="minimum-goals" value={minGoals} onChange={e => setMinGoals(Number(e.target.value))}>{[1,2,3,4,5].map(n => <option key={n} value={n}>{n}</option>)}</select>
      <label className="choice"><input type="checkbox" checked={late} onChange={e => setLate(e.target.checked)} />Allow employee submission after the deadline</label>
      <p className="muted">Contributions and development narratives are optional at submission. Every entered goal or contribution needs a description and an achievement narrative. Settings and reviewer assignments are frozen on activation.</p>
      <fieldset className="picker" disabled={busy || selecting !== null}><legend>Participants · {selected.size} selected</legend>
        <p className="muted">Bulk selection covers all pages and ignores the search. It adds active accounts with an active reporting manager who has the Manager role.</p>
        <div className="action-bar">
          <button className="button small" type="button" onClick={() => void selectRole('EMPLOYEE')}>Select all employees</button>
          <button className="button small" type="button" onClick={() => void selectRole('MANAGER')}>Select all managers</button>
          <button className="button small" type="button" disabled={!selected.size} onClick={() => { setSelected(new Set()); setSelectionNotice(''); setSelectionError(''); }}>Clear selection</button>
        </div>
        {selecting && <p role="status">Selecting participants…</p>}
        {selectionNotice && <Feedback message={selectionNotice} success />}
        {selectionError && <Feedback message={selectionError} />}
        <label htmlFor="participant-search">Find employees</label><input id="participant-search" value={search} onChange={e => { setSearch(e.target.value); setPage(1); }} />{lookupError && <Feedback message={lookupError} />}
        <div className="picker-list">{data?.items.map(person => <label className="choice" key={person.id}><input type="checkbox" checked={selected.has(person.id)} onChange={e => setSelected(current => { const next = new Set(current); if (e.target.checked) next.add(person.id); else next.delete(person.id); return next; })} />{person.full_name} <small>{person.employee_id} · {person.role}{!person.manager_id ? ' · Manager not assigned' : ''}</small></label>)}</div>{data && <Pagination page={page} total={data.total} onPage={setPage} />}</fieldset>
      <button className="button primary" type="submit" disabled={busy || selecting !== null}>{busy ? 'Saving…' : 'Save draft cycle'}</button></form></section>;
}
