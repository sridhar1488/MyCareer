import { useId } from 'react';
import type { components } from '../../api/schema';
import { Feedback } from '../../components/Feedback';

const stages = [
  ['NOT_STARTED', 'Not started'],
  ['DRAFT', 'Employee draft'],
  ['SUBMITTED', 'Submitted to manager'],
  ['UNDER_REVIEW', 'Under manager review'],
  ['RETURNED_FOR_REVISION', 'Returned for revision'],
  ['HR_REVIEW', 'Waiting for HR approval'],
  ['HR_APPROVED', 'Approved, awaiting release'],
  ['FINALIZED', 'Previously approved'],
  ['RELEASED', 'Released, awaiting receipt'],
  ['ACKNOWLEDGED', 'Acknowledged'],
] as const;

export type WorkflowSummary = Pick<components['schemas']['MonitorResponse'], 'total' | 'status_counts'>;
export type WorkflowScope = 'organization' | 'team';
export type WorkflowData = { data: WorkflowSummary | null; error: string; loading: boolean };

const percentage = new Intl.NumberFormat(undefined, { style: 'percent', maximumSignificantDigits: 3 });

export function WorkflowChart({ scope, data, error, loading, onScopeChange }: WorkflowData & {
  scope: WorkflowScope; onScopeChange?: (scope: WorkflowScope) => void;
}) {
  const headingId = useId();
  const team = scope === 'team';
  return <section className="panel workflow-chart" aria-labelledby={headingId}>
    <div className="section-heading">
      <div className="workflow-chart-heading">
        <h2 id={headingId}>{team ? 'Team appraisal workflow by stage' : 'Appraisal workflow by stage'}</h2>
        <p className="muted section-intro">{team ? 'Current status of appraisals assigned to you across all cycles.' : 'Current status across all appraisal cycles.'}</p>
      </div>
      {(onScopeChange || data) && <div className="workflow-chart-controls">
        {onScopeChange && <label className="workflow-scope">Workflow scope
          <select value={scope} onChange={event => onScopeChange(event.target.value === 'organization' ? 'organization' : 'team')}>
            <option value="team">My team</option>
            <option value="organization">Organization</option>
          </select>
        </label>}
        {data && <p className="muted section-intro"><strong>{data.total.toLocaleString()}</strong> total</p>}
      </div>}
    </div>
    {loading && <p role="status">Loading workflow counts…</p>}
    {error && <Feedback message={error} />}
    {data?.total === 0 && <p className="muted section-intro">{team ? 'No team appraisals have been assigned to you yet.' : 'No appraisals have been assigned yet.'}</p>}
    {data && data.total > 0 && <ul className="workflow-stage-list" aria-label="Appraisal counts by stage">
      {stages.map(([stage, label]) => {
        const count = data.status_counts[stage] ?? 0;
        if (stage === 'FINALIZED' && count === 0) return null;
        const share = count / data.total;
        return <li key={stage} className="workflow-stage" data-stage={stage}>
          <span className="workflow-stage-label">{label}</span>
          <div className="chart-track" aria-hidden="true"><span style={{ width: `${share * 100}%` }} /></div>
          <span className="workflow-stage-value"><strong>{count.toLocaleString()}</strong><span className="muted">{percentage.format(share)}</span></span>
        </li>;
      })}
    </ul>}
  </section>;
}
