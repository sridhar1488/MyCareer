import { useState } from 'react';
import { navigation, workspaceHref, type Page } from '../../app/navigation';
import { useApi } from '../../api/useApi';
import { LineIcon } from '../../components/LineIcon';
import { WelcomeBanner } from '../../components/WelcomeBanner';
import { teamAppraisalParams } from '../reviews/teamFilters';
import { WorkflowChart, type WorkflowData, type WorkflowScope, type WorkflowSummary } from './WorkflowChart';

type Navigate = (page: Page, teamStatus?: string) => boolean;
type CardLink = {
  title: string; action: string; page: Page;
  teamStatus?: string; accent?: 'amber' | 'green'; icon?: string;
};
type Card = CardLink & { endpoint: string };

function teamCountEndpoint(status = '') {
  return `/manager/appraisals?${new URLSearchParams({ page_size: '1', ...teamAppraisalParams(status) })}`;
}

const organizationCard: CardLink = { title: 'Organization appraisals', action: 'View HR monitoring', page: 'monitor' };
const hrCards: Card[] = [
  { title: 'Waiting for HR approval', action: 'Open approval queue', page: 'calibrations',
    endpoint: '/hr/calibrations?page_size=1', accent: 'amber' },
  { title: 'Approved evaluations', action: 'View evaluations', page: 'reports',
    endpoint: '/hr/evaluations?page_size=1', accent: 'green', icon: 'M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0 M8 12l3 3 5-6' },
];

const assignedCard: CardLink = { title: 'Assigned appraisals', action: 'View team appraisals', page: 'team' };
const managerCards: Card[] = [
  { title: 'Ready for review', action: 'View submissions', page: 'team', teamStatus: 'SUBMITTED',
    endpoint: teamCountEndpoint('SUBMITTED'), icon: navigation.personal.icon },
  { title: 'Reviews in progress', action: 'View open reviews', page: 'team', teamStatus: 'UNDER_REVIEW',
    endpoint: teamCountEndpoint('UNDER_REVIEW'), icon: 'M12 21H5V3h10l4 4v4 M14 3v5h5 M13 18l5-5 3 3-5 5h-3z' },
  { title: 'Ready for release', action: 'View release queue', page: 'team', teamStatus: 'READY_FOR_RELEASE',
    endpoint: teamCountEndpoint('READY_FOR_RELEASE'), icon: 'M22 2 9 15 M22 2 15 22l-6-7-7-6z' },
];

function DashboardCard({ card, navigate, data, error, loading }: {
  card: CardLink; navigate: Navigate; data: { total: number } | null; error: string; loading: boolean;
}) {
  const accent = data?.total === 0 ? 'neutral' : card.accent ?? 'purple';
  return <a className="dashboard-card" data-accent={accent} href={workspaceHref(card.page, card.teamStatus)}
    aria-busy={loading || undefined} onClick={event => {
      if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      event.preventDefault();
      navigate(card.page, card.teamStatus);
    }}>
    <span className="dashboard-card-icon"><LineIcon path={card.icon ?? navigation[card.page].icon} /></span>
    <span className="dashboard-card-title">
      <strong>{card.title}</strong>
      {error && <small className="muted">Count unavailable</small>}
    </span>
    <span className="dashboard-count">{data?.total.toLocaleString() ?? '—'}</span>
    <span className="dashboard-card-action">{card.action}</span>
    <span className="dashboard-card-arrow"><LineIcon path="M4 12h15m-6-6 6 6-6 6" /></span>
  </a>;
}

function LiveDashboardCard({ card, navigate }: { card: Card; navigate: Navigate }) {
  const { data, error, loading } = useApi<{ total: number }>(card.endpoint);
  return <DashboardCard card={card} navigate={navigate} data={data} error={error} loading={loading} />;
}

function ManagerDashboard({ navigate, organization }: { navigate: Navigate; organization?: WorkflowData }) {
  const [scope, setScope] = useState<WorkflowScope>(organization ? 'organization' : 'team');
  const { data: counts, error, loading } = useApi<WorkflowSummary['status_counts']>('/manager/dashboard?by_stage=true');
  const data = counts && { total: Object.values(counts).reduce((sum, count) => sum + count, 0), status_counts: counts };
  const activeScope = organization ? scope : 'team';
  const workflow = activeScope === 'organization' && organization ? organization : { data, error, loading };
  return <>
    <section className="dashboard-section">
      <h2>Manager dashboard</h2>
      <div className="dashboard-grid dashboard-grid-manager">
        <DashboardCard card={assignedCard} navigate={navigate} data={data} error={error} loading={loading} />
        {managerCards.map(card => <LiveDashboardCard key={card.title} card={card} navigate={navigate} />)}
      </div>
    </section>
    <WorkflowChart scope={activeScope} {...workflow} onScopeChange={organization ? setScope : undefined} />
  </>;
}

function HrDashboard({ manager, navigate }: { manager: boolean; navigate: Navigate }) {
  const { data, error, loading } = useApi<WorkflowSummary>('/hr/monitor?page_size=1');
  return <>
    <section className="dashboard-section">
      <h2>HR dashboard</h2>
      <div className="dashboard-grid dashboard-grid-hr">
        <DashboardCard card={organizationCard} navigate={navigate} data={data} error={error} loading={loading} />
        {hrCards.map(card => <LiveDashboardCard key={card.title} card={card} navigate={navigate} />)}
      </div>
    </section>
    {manager ? <ManagerDashboard navigate={navigate} organization={{ data, error, loading }} />
      : <WorkflowChart scope="organization" data={data} error={error} loading={loading} />}
  </>;
}

export function WorkspaceDashboard({ name, manager, hr, navigate }: { name: string; manager: boolean; hr: boolean; navigate: Navigate }) {
  return <>
    <WelcomeBanner name={name} message="See what needs your attention across your appraisals." />
    {hr ? <HrDashboard manager={manager} navigate={navigate} /> : manager && <ManagerDashboard navigate={navigate} />}
  </>;
}
