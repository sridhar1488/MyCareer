import { useEffect, useRef } from 'react';
import type { User } from '../api/client';
import { LineIcon } from '../components/LineIcon';
import { navigation, type Page } from './navigation';

export function ProfileAvatar({ user }: { user: User }) {
  const initials = user.full_name.trim().split(/\s+/).slice(0, 2).map(name => name[0]).join('').toUpperCase();
  return <span className="profile-avatar" aria-hidden="true">
    <span>{initials}</span>
    {user.profile_photo_revision &&
      <img key={user.profile_photo_revision} src={`/api/v1/auth/me/photo?v=${encodeURIComponent(user.profile_photo_revision)}`}
        alt="" onError={event => { event.currentTarget.hidden = true; }} />}
  </span>;
}

const roleLabels: Record<string, string> = {
  SUPER_ADMIN: 'Super Admin', MANAGER: 'Manager', EMPLOYEE: 'Employee', HR: 'HR',
};

export function WorkspaceHeader({ user, page, profileItems, navigate, logout, busy }: {
  user: User; page: Page; profileItems: Page[]; navigate: (page: Page) => boolean; logout: () => void; busy: boolean;
}) {
  const menu = useRef<HTMLDetailsElement>(null);
  useEffect(() => {
    function closeOutside(event: PointerEvent) {
      if (menu.current?.open && !menu.current.contains(event.target as Node)) menu.current.open = false;
    }
    document.addEventListener('pointerdown', closeOutside);
    return () => document.removeEventListener('pointerdown', closeOutside);
  }, []);

  return <header className="topbar">
    <span className="workspace-product">MyCareer</span>
    <div className="topbar-actions">
      {profileItems.length ? <details className="profile-menu" ref={menu} onKeyDown={event => {
        if (event.key === 'Escape' && event.currentTarget.open) {
          event.currentTarget.open = false;
          event.currentTarget.querySelector('summary')?.focus();
        }
      }}>
        <summary aria-label="User profile">
          <ProfileAvatar user={user} />
          <span className="profile-identity"><strong>{user.full_name}</strong><small>{user.roles.map(role => roleLabels[role] ?? role).join(' · ')}</small></span>
          <LineIcon path="m6 9 6 6 6-6" />
        </summary>
        <nav className="profile-links" aria-label="Profile navigation">
          {profileItems.map(key => <button key={key} type="button" aria-current={page === key ? 'page' : undefined} onClick={() => {
            if (navigate(key) && menu.current) {
              menu.current.open = false;
              menu.current.querySelector('summary')?.focus({ preventScroll: true });
            }
          }}><LineIcon path={navigation[key].icon} />{navigation[key].label}</button>)}
        </nav>
      </details> : <span className="profile-identity"><strong>{user.full_name}</strong><small>{user.roles.map(role => roleLabels[role] ?? role).join(' · ')}</small></span>}
      <button className="button small sign-out-button" onClick={logout} disabled={busy}>
        <LineIcon path="M10 4H4v16h6 M9 12h12 m-4-4 4 4-4 4" />
        {busy ? 'Signing out…' : 'Sign out'}
      </button>
    </div>
  </header>;
}
