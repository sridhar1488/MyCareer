import {useState} from 'react';
import type {components} from '../../api/schema';
import {api} from '../../api/client';
import {useApi} from '../../api/useApi';
import {Feedback} from '../../components/Feedback';
import {localDateTime} from '../../utils/dates';
import {ScoreSummary} from './ScoreSummary';
import {ReviewHistoryEntry} from './ReviewHistoryEntry';

export function ReleasedEvaluation({appraisalId}: {appraisalId:string}) {
  const [revision,setRevision] = useState(0);const [busy,setBusy] = useState(false);const [error,setError] = useState('');
  const {data,error:loadError,loading} = useApi<components['schemas']['ReleasedResult']>(`/appraisals/${appraisalId}/released-result`,revision);
  async function acknowledge() {if(!data)return;setBusy(true);setError('');try{await api(`/appraisals/${appraisalId}/acknowledge`,'POST',{expected_version:data.appraisal_version});setRevision(revision+1);}catch(e){setError((e as Error).message);}finally{setBusy(false);}}
  return <>{(error || loadError) && <Feedback message={error || loadError} />}{loading && <p role="status">Loading released evaluation…</p>}{data && <><section className="panel"><p className="eyebrow">RELEASED EVALUATION</p><h2>Your HR approved evaluation</h2><p>Approved {localDateTime(data.finalized_at)} · Released {localDateTime(data.released_at)}</p><p>Employee submission revision {data.submitted_revision} · Reporting manager {String(data.identity_snapshot.manager_name)}</p></section><ScoreSummary score={data.score} /><section className="panel"><h2>Manager ratings and feedback</h2><ReviewHistoryEntry evaluation={data.evaluation} competencies={data.form_definition.competencies as string[]} definition={data.form_definition} /></section><section className="panel"><h2>Employee acknowledgement</h2>{data.acknowledged_at ? <p role="status">Receipt acknowledged on {localDateTime(data.acknowledged_at)}.</p> : <><p>Acknowledgement records that you received this evaluation. It leaves the final score unchanged.</p><button className="button primary" disabled={busy} onClick={acknowledge}>{busy ? 'Recording receipt…' : 'I acknowledge receipt'}</button></>}</section></>}</>;
}
