import { useState } from 'react';
import { api, type User } from '../../api/client';
import { ProfileAvatar } from '../../app/WorkspaceHeader';
import { Feedback } from '../../components/Feedback';
import { calendarDate } from '../../utils/dates';

export function MyProfile({ user, onChange }: { user: User; onChange: (user: User) => void }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  async function updatePhoto(file?: File) {
    setError(''); setNotice('');
    if (file && file.size > 2 * 1024 * 1024) {
      setError('Choose an image of 2 MB or less.');
      return;
    }
    setBusy(true);
    try {
      onChange(await api<User>('/auth/me/photo', file ? 'PUT' : 'DELETE', file));
      setNotice(file ? 'Profile picture updated.' : 'Profile picture removed.');
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return <section className="panel">
    <div className="section-heading"><h2>Profile details</h2><span className="status-dot">Account active</span></div>
    {error && <Feedback message={error} />}{notice && <Feedback message={notice} success />}
    <div className="profile-photo-controls">
      <ProfileAvatar user={user} />
      <div>
        <label htmlFor="profile-photo">{user.profile_photo_revision ? 'Change profile picture' : 'Add profile picture'}</label>
        <input id="profile-photo" type="file" accept="image/jpeg,image/png,image/webp" disabled={busy}
          aria-describedby="profile-photo-hint" onChange={event => {
            const file = event.currentTarget.files?.[0];
            event.currentTarget.value = '';
            if (file) void updatePhoto(file);
          }} />
        <small id="profile-photo-hint" className="muted">JPEG, PNG, or WebP. Up to 2 MB.</small>
      </div>
      {user.profile_photo_revision && <button className="button" disabled={busy} onClick={() => void updatePhoto()}>Remove profile picture</button>}
    </div>
    <dl className="profile-grid">{[
      ['Full name', user.full_name],
      ['Employee ID', user.employee_id],
      ['Work email', user.email],
      ['Department', user.department || 'Not provided'],
      ['Designation', user.designation || 'Not provided'],
      ['Country', user.country?.trim() || 'India'],
      ['Joining date', user.date_joined ? calendarDate(user.date_joined) : 'Not provided'],
      ['Current reporting manager', user.manager_name || 'Not assigned'],
    ].map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl>
  </section>;
}
