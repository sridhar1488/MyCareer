import { useState } from 'react';
import type { components } from '../../api/schema';
import { api } from '../../api/client';
import { useApi } from '../../api/useApi';
import { Feedback } from '../../components/Feedback';
import { localDateTime } from '../../utils/dates';
import { cycleLabel } from '../../utils/labels';

export function ReleasedEvaluation({ appraisalId, onAcknowledged }: {
  appraisalId: string;
  onAcknowledged?: (acknowledgedAt: string, version: number) => void;
}) {
  const [revision, setRevision] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const { data, error: loadError, loading } = useApi<components['schemas']['EmployeeReleasedResult']>(
    `/appraisals/${appraisalId}/released-result`, revision,
  );

  async function acknowledge() {
    if (!data) return;
    setBusy(true);
    setError('');
    try {
      const result = await api<components['schemas']['EmployeeReleasedResult']>(
        `/appraisals/${appraisalId}/acknowledge`, 'POST', { expected_version: data.appraisal_version },
      );
      if (result.acknowledged_at) onAcknowledged?.(result.acknowledged_at, result.appraisal_version);
      setRevision(value => value + 1);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return <>
    {(error || loadError) && <Feedback message={error || loadError} />}
    {loading && <p role="status">Loading released evaluation…</p>}
    {data && <>
      <section className="panel">
        <p className="eyebrow">RELEASED EVALUATION</p>
        <h2>Your final evaluation</h2>
        <p>{cycleLabel(data.cycle_title)}</p>
      </section>
      <section className="panel score-summary released-score-card" aria-labelledby="released-score-title">
        <div className="released-score-main">
          <h2 id="released-score-title">Overall performance score</h2>
          <p className="released-score-value">{data.overall_score} <span>/ 5</span></p>
        </div>
        <div className="released-score-details">
          <strong>Final evaluation</strong>
          <time dateTime={data.released_at}>{localDateTime(data.released_at)}</time>
          <p>Released to you</p>
        </div>
      </section>
      <section className="panel">
        <h2>Manager feedback</h2>
        {data.feedback.map((section, index) => <section key={index}>
          <h3>{section.title}</h3>
          {section.items.map((item, itemIndex) => <p className="review-text" key={itemIndex}>
            <strong>{item.label}</strong><br />{item.comment || 'No feedback provided.'}
          </p>)}
        </section>)}
      </section>
      <section className="panel">
        <h2>Employee acknowledgement</h2>
        {data.acknowledged_at ? <p role="status">Receipt acknowledged on {localDateTime(data.acknowledged_at)}.</p> : <>
          <p>Acknowledgement records that you received this evaluation.</p>
          <button className="button primary" disabled={busy} onClick={acknowledge}>
            {busy ? 'Recording receipt…' : 'I acknowledge receipt'}
          </button>
        </>}
      </section>
    </>}
  </>;
}
