import { useState } from 'react';
import { api, downloadFile } from '../../api/client';
import { Feedback } from '../../components/Feedback';
import { localDateTime } from '../../utils/dates';
import { useApi } from '../../api/useApi';

type Attachment = {id:string;name:string;media_type:string;size:number;uploaded_at:string;submitted_revision:number|null};
const accepted = '.pdf,.png,.jpg,.jpeg,.docx,.xlsx,.pptx';
export function Attachments({appraisalId,editable=false}:{appraisalId:string;editable?:boolean}) {
  const [revision,setRevision]=useState(0); const [busy,setBusy]=useState(false); const [error,setError]=useState(''); const [notice,setNotice]=useState('');
  const {data,error:loadError}=useApi<{items:Attachment[]}>(`/appraisals/${appraisalId}/attachments`,revision); const items=data?.items??[];
  function load(){setRevision(value=>value+1);}
  async function upload(files:FileList|null){if(!files?.length)return;setBusy(true);setError('');setNotice('');try{for(const file of Array.from(files)){if(file.size>10*1024*1024)throw new Error(`${file.name} is larger than the 10 MB limit.`);await api(`/appraisals/${appraisalId}/attachments`,'POST',file,{'X-File-Name':encodeURIComponent(file.name)});}load();setNotice('Supporting documents uploaded.');}catch(e){setError((e as Error).message);}finally{setBusy(false);}}
  async function remove(item:Attachment){setBusy(true);setError('');try{await api(`/appraisals/${appraisalId}/attachments/${item.id}`,'DELETE');load();}catch(e){setError((e as Error).message);}finally{setBusy(false);}}
  return <section className="panel"><h2>Supporting documents</h2><p>Attach certifications, appreciations, client feedback or other evidence (PDF, image, Word, Excel or PowerPoint; up to 10 MB each).</p>
    {(error||loadError)&&<Feedback message={error||loadError}/ >}{notice&&<Feedback message={notice} success/>}
    {editable&&<label htmlFor={`attachments-${appraisalId}`}>Add files<input id={`attachments-${appraisalId}`} type="file" accept={accepted} multiple disabled={busy} onChange={e=>{void upload(e.target.files);e.target.value='';}}/></label>}
    {items.length? <ul className="attachment-list">{items.map(item=><li key={item.id}><div><strong>{item.name}</strong><small>{Math.max(1,Math.round(item.size/1024))} KB · {item.submitted_revision?`Submitted revision ${item.submitted_revision}`:`Draft attachment`} · {localDateTime(item.uploaded_at)}</small></div><div className="action-bar"><button className="text-button" disabled={busy} onClick={()=>void downloadFile(`/appraisals/${appraisalId}/attachments/${item.id}`,item.name)}>Download</button>{editable&&!item.submitted_revision&&<button className="text-button" disabled={busy} onClick={()=>void remove(item)}>Remove</button>}</div></li>)}</ul>:<p className="muted">No supporting documents added.</p>}
  </section>;
}
