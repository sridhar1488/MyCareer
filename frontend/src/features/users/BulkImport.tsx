import { useState } from 'react';
import { api, downloadFile } from '../../api/client';
import type { components } from '../../api/schema';
import { Feedback } from '../../components/Feedback';
import { localDateTime } from '../../utils/dates';

export function BulkImport({ onClose }: { onClose: () => void }) {
  const [preview, setPreview] = useState<components['schemas']['ImportPreview'] | null>(null);
  const [result, setResult] = useState<components['schemas']['ImportResult'] | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  async function upload(file?: File) {
    if (!file) return;
    setBusy(true);
    setError('');
    setPreview(null);
    try {
      setPreview(await api('/admin/user-imports/preview', 'POST', file));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function confirm() {
    if (!preview?.batch_id) return;
    setBusy(true);
    setError('');
    try {
      setResult(await api(`/admin/user-imports/${preview.batch_id}/confirm`, 'POST'));
      setPreview(null);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const columns: [string, string][] = [
    ['Employee Number', 'employee_id'],
    ['Full Name', 'full_name'],
    ['Work Email', 'email'],
    ['Location', 'location'],
    ['Department', 'department'],
    ['Job Title', 'designation'],
    ['Reporting To', 'manager_employee_id'],
    ['Date Joined', 'date_joined'],
    ['Assigned role', 'role'],
  ];

  return (
    <section className="panel">
      <div className="action-bar">
        <h2>Bulk Excel user import</h2>
        <button className="button" disabled={busy} onClick={() => {
          if (!result || window.confirm('Have you securely handed off or copied the setup links? They cannot be viewed again.')) onClose();
        }}>Back to directory</button>
      </div>
      {error && <Feedback message={error} />}
      <p>
        Upload the HRMS workbook with Employee Number, Full Name, Work Email, Location, Department,
        Job Title, Reporting To, and Date Joined. The template supports up to 200 new users. Managers
        are inferred from reporting relationships; HR / Super Admin accounts are created separately.
        Existing accounts and duplicate IDs or emails are rejected. No accounts are created until you
        confirm the validated preview.
      </p>
      {!result && <>
        <button className="button" disabled={busy} onClick={() => downloadFile('/admin/user-imports/template', 'mycareer-hrms-user-import.xlsx').catch(e => setError(e.message))}>
          Download HRMS-format Excel template
        </button>
        <label htmlFor="import-file">Upload completed Excel workbook (.xlsx, maximum 5 MB)</label>
        <input id="import-file" type="file" accept=".xlsx" disabled={busy} onChange={e => upload(e.target.files?.[0])} />
      </>}
      {preview && <>
        <h3>Validation preview · {preview.rows.length} rows</h3>
        {preview.errors.length > 0
          ? <ul>{preview.errors.map((item, index) => <li key={index}>Row {item.row}: {item.message}</li>)}</ul>
          : <p>All rows validated. Preview expires {localDateTime(preview.expires_at)}.</p>}
        <div className="table-scroll"><table>
          <thead><tr>{columns.map(([label]) => <th key={label}>{label}</th>)}</tr></thead>
          <tbody>{preview.rows.map((row, index) => <tr key={index}>
            {columns.map(([, key]) => <td key={key}>{String(row[key] ?? '')}</td>)}
          </tr>)}</tbody>
        </table></div>
        <button className="button primary" disabled={busy || !preview.batch_id || preview.errors.length > 0} onClick={confirm}>
          Confirm and create {preview.rows.length} users
        </button>
      </>}
      {result && <>
        <Feedback success message={`${result.created} accounts created.`} />
        <h3>Private one-time setup links</h3>
        <p>When live email is enabled, each employee also receives a setup email automatically. Copy and privately share a link only if email is disabled or a handoff is needed. Links expire at the times shown and work once. They are shown only in this response. If one is lost or expires, create a new setup link from the directory.</p>
        {result.setup_links.map(link => <div className="review-item" key={link.user_id}>
          <strong>{link.full_name} · {link.email}</strong>
          <label htmlFor={`link-${link.user_id}`}>Private setup link · expires {localDateTime(link.expires_at)}</label>
          <input id={`link-${link.user_id}`} readOnly value={link.setup_url} onFocus={e => e.target.select()} />
          <button className="button small" onClick={() => navigator.clipboard.writeText(link.setup_url).catch(() => setError('Select and copy the link manually.'))}>
            Copy link for {link.full_name}
          </button>
        </div>)}
      </>}
    </section>
  );
}
