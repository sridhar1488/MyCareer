import { useState } from 'react';
import { useApi } from '../../api/useApi';
import { Feedback } from '../../components/Feedback';
import { BellCurve } from './BellCurve';
import type { components } from '../../api/schema';

type CycleOption = { id: string; label: string };
type Analytics = components['schemas']['AnalyticsResponse'];

function scoreWidth(score: string | null) {
  return Math.max(0, Math.min(100, (Number(score ?? 0) / 5) * 100));
}

export function AnalyticsDashboard({ cycles, revision }: { cycles: CycleOption[]; revision: number }) {
  const [cycle, setCycle] = useState('');
  const params = new URLSearchParams(cycle ? { cycle_id: cycle } : {});
  const { data, error, loading } = useApi<Analytics>(`/hr/analytics?${params}`, revision);

  return <section className="panel hr-analytics">
    <div className="section-heading">
      <div><h2>People and performance analytics</h2><p className="muted">Scores include HR-approved evaluations only. Workflow progress counts all appraisals in scope.</p></div>
      <label className="analytics-cycle">Cycle<select value={cycle} onChange={e => setCycle(e.target.value)}><option value="">All cycles</option>{cycles.map(c => <option key={c.id} value={c.id}>{c.label}</option>)}</select></label>
    </div>
    {error && <Feedback message={error} />}
    {loading && <p role="status">Loading analytics…</p>}
    {data && <>
      <div className="analytics-kpis">
        <div><span>Appraisals in scope</span><strong>{data.summary.appraisal_count}</strong></div>
        <div><span>HR approved</span><strong>{data.summary.approved_count}<small> / {data.summary.appraisal_count} · {data.summary.approval_percent}%</small></strong></div>
        <div><span>Average approved score</span><strong>{data.summary.approved_average ? `${data.summary.approved_average} / 5` : '—'}</strong></div>
      </div>
      <BellCurve points={data.score_points} />
      <div className="analytics-charts">
        <section className="analytics-chart" aria-labelledby="top-performers-heading">
          <h3 id="top-performers-heading">Top 5 performers</h3>
          <p className="muted">Ranked by average score across approved appraisals in this selection.</p>
          {data.top_performers.length ? <ol className="performer-list">{data.top_performers.map(person => <li key={person.employee_id}>
            <div className="chart-label"><span><strong>{person.employee_name}</strong><small>{person.department} · {person.manager_name} · {person.approved_appraisals} approved {person.approved_appraisals === 1 ? 'appraisal' : 'appraisals'}</small></span><b>{person.average_score}<small> / 5</small></b></div>
            <div className="chart-track" role="img" aria-label={`${person.employee_name}: ${person.average_score} out of 5`}><span style={{ width: `${scoreWidth(person.average_score)}%` }} /></div>
          </li>)}</ol> : <p>No HR-approved evaluations are available for this selection yet.</p>}
        </section>
        <section className="analytics-chart" aria-labelledby="department-heading">
          <h3 id="department-heading">Department score comparison</h3>
          <p className="muted">Average scores use HR-approved evaluations. The label under each department shows its approval progress.</p>
          {data.departments.length ? <div className="department-plot">
            <div className="department-y-axis" aria-hidden="true"><span>5</span><span>4</span><span>3</span><span>2</span><span>1</span><span>0</span></div>
            <div className="department-plot-content">
              <div className="department-bars" style={{ gridTemplateColumns: `repeat(${data.departments.length}, minmax(0, 1fr))` }}>{data.departments.map(department => <div className="department-bar-column" key={department.department} role="img" aria-label={`${department.department}: ${department.average_score ? `average score ${department.average_score} out of 5` : 'no approved score'}; ${department.approved_count} of ${department.appraisal_count} approved`}>
                {department.average_score && <><span className="department-bar-value" style={{ bottom: `calc(${scoreWidth(department.average_score)}% + 5px)` }}>{department.average_score}</span><span className="department-bar" style={{ height: `${scoreWidth(department.average_score)}%` }} /></>}
              </div>)}</div>
              <div className="department-labels" style={{ gridTemplateColumns: `repeat(${data.departments.length}, minmax(0, 1fr))` }}>{data.departments.map(department => <div key={department.department}>
                <strong title={department.department}>{department.department}</strong>
                <small>{department.approved_count} / {department.appraisal_count} approved</small>
                <small>{department.approval_percent}% complete</small>
              </div>)}</div>
            </div>
          </div> : <p>No appraisals are available for this selection.</p>}
          {data.departments.length > 0 && <p className="department-chart-scale">Average approved score · scale from 0 to 5</p>}
        </section>
      </div>
    </>}
  </section>;
}
