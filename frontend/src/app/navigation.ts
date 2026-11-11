export const navigation = {
  dashboard: { label: 'Dashboard', icon: 'M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z' },
  personal: { label: 'My appraisal', icon: 'M8 5H5v16h14V5h-3 M8 3h8v4H8z M8 11h8 M8 15h8' },
  team: { label: 'Team appraisals', icon: 'M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2 M13 7a4 4 0 1 1-8 0 4 4 0 0 1 8 0 M22 21v-2a4 4 0 0 0-3-4 M16 3a4 4 0 0 1 0 8' },
  calibrations: { label: 'HR approval queue', icon: 'M3 3h18v18H3z M7 12l3 3 7-7' },
  monitor: { label: 'HR monitoring', icon: 'M3 13h4v8H3z M10 8h4v13h-4z M17 3h4v18h-4z' },
  reports: { label: 'Final evaluations', icon: 'M6 3h9l4 4v14H6z M14 3v5h5 M9 12h7 M9 16h7' },
  forms: { label: 'Appraisal forms', icon: 'm12 3 9 5-9 5-9-5z M3 12l9 5 9-5 M3 16l9 5 9-5' },
  cycles: { label: 'Appraisal cycles', icon: 'M3 6h18v15H3z M7 3v6 M17 3v6 M3 11h18 M8 15h2 M14 15h2' },
  help: { label: 'Help & Support', icon: 'M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0 M9 9a3 3 0 1 1 4 2.8c-.7.3-1 .8-1 1.7 M12 17h.01' },
  profile: { label: 'Your profile', icon: 'M16 7a4 4 0 1 1-8 0 4 4 0 0 1 8 0 M4 21v-2a5 5 0 0 1 5-5h6a5 5 0 0 1 5 5v2' },
  security: { label: 'Account security', icon: 'm12 22 4-3c3-2 4-5 4-9V5l-8-3-8 3v5c0 4 1 7 4 9z M8 12l3 3 5-6' },
  users: { label: 'User directory', icon: 'M4 3h16v18H4z M7 7h10 M7 11h10 M7 15h6' },
  admin: { label: 'Account overview', icon: 'M3 5h18v14H3z M7 9h4 M7 15h4 M15 9h2 M15 15h2' },
  audit: { label: 'Account audit log', icon: 'M4 3h16v18H4z M8 8h8 M8 12h8 M8 16h5' },
} as const;

export type Page = keyof typeof navigation;

export type WorkspaceDestination = { page: Page; teamStatus: string };

export function workspaceDestination(defaultPage: Page = 'personal'): WorkspaceDestination {
  const params = new URLSearchParams(window.location.search);
  const view = params.get('view');
  const page = view && Object.hasOwn(navigation, view) ? view as Page : defaultPage;
  const status = params.get('status') ?? '';
  const teamStatus = page === 'team' && ['SUBMITTED', 'UNDER_REVIEW', 'READY_FOR_RELEASE'].includes(status)
    ? status : '';
  return { page, teamStatus };
}

export function workspaceHref(page?: Page, teamStatus = '') {
  const url = new URL(window.location.href);
  if (page) url.searchParams.set('view', page);
  else url.searchParams.delete('view');
  if (page === 'team' && teamStatus) url.searchParams.set('status', teamStatus);
  else url.searchParams.delete('status');
  return url.pathname + url.search;
}
