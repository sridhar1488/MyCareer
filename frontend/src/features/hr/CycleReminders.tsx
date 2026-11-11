import { useState, type FormEvent } from 'react';
import { api } from '../../api/client';
import type { components } from '../../api/schema';
import { useApi } from '../../api/useApi';
import { Feedback } from '../../components/Feedback';
import { localDateTime } from '../../utils/dates';

type Settings = components['schemas']['ReminderSettingsResponse'];
type Selection = components['schemas']['ReminderSelection'];
type Preview = components['schemas']['ReminderPreview'];
const offsets = [[168, '7 days'], [72, '3 days'], [24, '1 day'], [8, '8 hours']] as const;

function localInput(value: string | null) {
  if (!value) return '';
  const date = new Date(/(?:Z|[+-]\d\d:\d\d)$/.test(value) ? value : `${value}Z`);
  return new Date(date.getTime() - date.getTimezoneOffset() * 60_000).toISOString().slice(0, 16);
}

function CycleReminderEditor({ endpoint, initial }: { endpoint: string; initial: Settings }) {
  const [settings, setSettings] = useState(initial);
  const [manager, setManager] = useState(localInput(initial.manager_deadline));
  const [hr, setHr] = useState(localInput(initial.hr_deadline));
  const [hours, setHours] = useState(initial.hours_before);
  const [stage, setStage] = useState<Selection['stage']>('employee');
  const [audience, setAudience] = useState<NonNullable<Selection['audience']>>('pending');
  const [preview, setPreview] = useState<Preview | null>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');

  async function save(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError(''); setNotice('');
    try {
      const saved = await api<Settings>(`${endpoint}/settings`, 'PUT', {
        expected_version: settings.version,
        manager_deadline: manager ? new Date(manager).toISOString() : null,
        hr_deadline: hr ? new Date(hr).toISOString() : null,
        hours_before: hours,
      });
      setSettings(saved); setPreview(null); setNotice('Reminder settings saved.');
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }

  async function showPreview(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError(''); setNotice(''); setPreview(null);
    try { setPreview(await api<Preview>(`${endpoint}/preview`, 'POST', { stage, audience })); }
    catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }

  async function send() {
    if (!preview || !window.confirm(`Queue reminders for ${preview.recipient_count} recipient(s)?`)) return;
    setBusy(true); setError(''); setNotice('');
    try {
      const result = await api<components['schemas']['ReminderSent']>(`${endpoint}/send`, 'POST', {
        stage, audience, request_id: preview.request_id, fingerprint: preview.fingerprint,
      });
      setNotice(`${result.queued} reminder${result.queued === 1 ? '' : 's'} queued${preview.mail_mode === 'test' ? ' for the test mailbox' : ''}.`);
      setPreview(null);
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }

  const editable = settings.state === 'DRAFT' || settings.state === 'ACTIVE';
  return <>
    {error && <Feedback message={error} />}
    {notice && <Feedback message={notice} success />}
    <form onSubmit={save}>
      <fieldset disabled={busy || !editable}>
        <legend>Scheduled reminders</legend>
        <p>Employee submission deadline: {localDateTime(settings.employee_deadline)}</p>
        <div className="form-grid">
          <label>Manager review deadline<input type="datetime-local" value={manager} onChange={e => setManager(e.target.value)} /></label>
          <label>HR calibration deadline<input type="datetime-local" value={hr} onChange={e => setHr(e.target.value)} /></label>
        </div>
        <p className="muted">Dates use your local time zone. Manager and HR deadlines guide reminders. Scheduled emails go to people with work pending in active cycles.</p>
        <div className="action-bar">
          {offsets.map(([offset, label]) => <label className="choice" key={offset}>
            <input type="checkbox" checked={hours.includes(offset)} onChange={e => setHours(e.target.checked ? [...hours, offset] : hours.filter(value => value !== offset))} />{label} before each deadline
          </label>)}
        </div>
        <p className="muted">Choose at least one interval to turn on scheduled reminders. Manager and HR reminders need their own deadlines.</p>
        <button className="button small" type="submit">Save reminder settings</button>
      </fieldset>
    </form>
    <form onSubmit={showPreview}>
      <fieldset disabled={busy || settings.state !== 'ACTIVE'}>
        <legend>Send a reminder</legend>
        {settings.state !== 'ACTIVE' && <p>Activate the cycle to send reminders.</p>}
        <div className="form-grid">
          <label>Reminder stage<select value={stage} onChange={e => { setStage(e.target.value as Selection['stage']); setPreview(null); }}>
            <option value="employee">Employee self-assessment</option><option value="manager">Manager review</option><option value="hr">HR calibration</option>
          </select></label>
          <label>Audience<select value={audience} onChange={e => { setAudience(e.target.value === 'all' ? 'all' : 'pending'); setPreview(null); }}>
            <option value="pending">People with work pending</option><option value="all">{stage === 'hr' ? 'All HR approvers' : 'All assigned participants'}</option>
          </select></label>
        </div>
        <button className="button small" type="submit">Preview reminder</button>
        {preview && <div className="reminder-preview">
          <h3>{preview.subject}</h3>
          <p className="muted">{preview.recipient_count.toLocaleString()} intended recipients · Counts are personalized.</p>
          <p className="review-text">{preview.body}</p>
          {preview.mail_mode === 'disabled' && <p>Email delivery is disabled.</p>}
          {preview.mail_mode === 'test' && <p>Test mode routes email to the configured test mailbox.</p>}
          <button className="button primary" type="button" disabled={!preview.recipient_count || preview.mail_mode === 'disabled'} onClick={() => void send()}>Send reminders</button>
        </div>}
      </fieldset>
    </form>
  </>;
}

function CycleReminderDetails({ cycle }: { cycle: string }) {
  const endpoint = `/hr/cycle-reminders/${encodeURIComponent(cycle)}`;
  const { data, error, loading } = useApi<Settings>(`${endpoint}/settings`);
  if (loading) return <p role="status">Loading reminder settings…</p>;
  if (error) return <Feedback message={error} />;
  return data && <CycleReminderEditor endpoint={endpoint} initial={data} />;
}

export function CycleReminders({ cycles }: { cycles: components['schemas']['FilterOption'][] }) {
  const [cycle, setCycle] = useState('');
  return <details className="panel cycle-reminders">
    <summary>Cycle reminders</summary>
    <label htmlFor="reminder-cycle">Appraisal cycle for reminders</label>
    <select id="reminder-cycle" value={cycle} onChange={e => setCycle(e.target.value)}>
      <option value="">Choose a cycle</option>
      {cycles.map(item => <option key={item.id} value={item.id}>{item.label}</option>)}
    </select>
    {cycle && <CycleReminderDetails key={cycle} cycle={cycle} />}
  </details>;
}
