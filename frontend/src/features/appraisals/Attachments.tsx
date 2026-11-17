import { useEffect, useState } from 'react';
import { ApiError, api, downloadFile } from '../../api/client';
import { Feedback } from '../../components/Feedback';
import { localDateTime } from '../../utils/dates';
import { useApi } from '../../api/useApi';

type Attachment = {id:string;name:string;media_type:string;size:number;uploaded_at:string;submitted_revision:number|null};
const accepted = '.pdf,.png,.jpg,.jpeg,.docx,.xlsx,.pptx,.msg';
export function Attachments({appraisalId,editable=false,disabled=false,forSubmission=false,onBusyChange,onReviewReady}:{appraisalId:string;editable?:boolean;disabled?:boolean;forSubmission?:boolean;onBusyChange?:(busy:boolean)=>void;onReviewReady?:(ready:boolean)=>void}) {
  const [revision,setRevision]=useState(0); const [busy,setBusy]=useState(false); const [error,setError]=useState(''); const [notice,setNotice]=useState(''); const [previewId,setPreviewId]=useState('');
  const {data,error:loadError,loading}=useApi<{items:Attachment[]}>(`/appraisals/${appraisalId}/attachments`,revision); const items=data?.items??[];
  useEffect(() => onReviewReady?.(Boolean(data)), [data, onReviewReady]);
  function load(){setRevision(value=>value+1);}
  function changeBusy(value:boolean){setBusy(value);onBusyChange?.(value);}
  async function upload(files:FileList|null) {
    if (!files?.length || busy || disabled) return;
    changeBusy(true); setError(''); setNotice('');
    const duplicates: string[] = [];
    let uploaded = false;
    let uploadError = '';
    try {
      for (const file of Array.from(files)) {
        if (!file.size) throw new Error(`${file.name} is empty. Choose a file with content.`);
        if (file.size > 10 * 1024 * 1024) throw new Error(`${file.name} is larger than the 10 MB limit.`);
        try {
          await api(`/appraisals/${appraisalId}/attachments`, 'POST', file, {'X-File-Name': encodeURIComponent(file.name)});
          uploaded = true;
        } catch (e) {
          if (!(e instanceof ApiError) || e.code !== 'DUPLICATE_ATTACHMENT') throw e;
          duplicates.push(e.message);
        }
      }
    } catch (e) {
      uploadError = (e as Error).message;
    } finally {
      if (uploaded) { load(); setNotice('Supporting documents uploaded.'); }
      const duplicateError = duplicates.length > 1 ? `Skipped ${duplicates.length} duplicate files.` : duplicates[0];
      setError([duplicateError, uploadError].filter(Boolean).join(' '));
      changeBusy(false);
    }
  }
  async function remove(item:Attachment){
    if (busy || disabled || !window.confirm(`Remove “${item.name}” from this appraisal?`)) return;
    changeBusy(true);setError('');setNotice('');
    try{
      await api(`/appraisals/${appraisalId}/attachments/${item.id}`,'DELETE');
      if (previewId === item.id) setPreviewId('');
      load();
    }catch(e){setError((e as Error).message);}finally{changeBusy(false);}
  }
  return <section className={forSubmission ? 'submission-attachments' : 'panel'}>{forSubmission ? <h3>Supporting documents</h3> : <h2>Supporting documents</h2>}
    {editable && <p>Up to 25 files, 10 MB each. Accepted formats: PDF, PNG, JPG, JPEG, DOCX, XLSX, PPTX and MSG.</p>}
    {editable && items.some(item => item.submitted_revision) && <p>Files from earlier submissions are locked to preserve the record. To correct a file, add the new file and tell your manager which earlier file it replaces.</p>}
    {forSubmission && <p>Review the evidence included with your appraisal, including files retained from earlier submissions.</p>}
    {(error||loadError)&&<Feedback message={error||loadError}/ >}{notice&&<Feedback message={notice} success/>}
    {loadError && <button className="button" onClick={load}>Retry loading supporting documents</button>}
    {editable&&<label htmlFor={`attachments-${appraisalId}`}>Add files<input id={`attachments-${appraisalId}`} type="file" accept={accepted} multiple disabled={busy||disabled} onChange={e=>{void upload(e.target.files);e.target.value='';}}/></label>}
    {loading ? <p role="status">Loading supporting documents…</p> : loadError ? null : items.length ? <ul className="attachment-list">{items.map(item=>{const previewable=['application/pdf','image/jpeg','image/png'].includes(item.media_type);const previewUrl=`/api/v1/appraisals/${appraisalId}/attachments/${item.id}?inline=true`;return <li key={item.id}><div><strong>{item.name}</strong><small>{Math.max(1,Math.round(item.size/1024))} KB · {item.submitted_revision?`Submitted revision ${item.submitted_revision}`:`Draft attachment`} · {localDateTime(item.uploaded_at)}</small></div><div className="attachment-actions"><div className="action-bar">{previewable&&<button className="text-button" aria-expanded={previewId===item.id} onClick={()=>setPreviewId(previewId===item.id?'':item.id)}>{previewId===item.id?'Close preview':'Preview'}</button>}<button className="text-button" disabled={busy} onClick={()=>void downloadFile(`/appraisals/${appraisalId}/attachments/${item.id}`,item.name).catch(e => setError((e as Error).message))}>Download</button>{editable&&!item.submitted_revision&&<button className="text-button" disabled={busy||disabled} onClick={()=>void remove(item)}>Remove</button>}</div>{previewId===item.id&&previewable&&<div className="attachment-preview">{item.media_type==='application/pdf'?<iframe title={`Preview of ${item.name}`} src={previewUrl} loading="lazy" referrerPolicy="no-referrer"/>:<img src={previewUrl} alt={`Preview of ${item.name}`} loading="lazy"/>}<a href={previewUrl} target="_blank" rel="noopener noreferrer">Open preview in a new tab</a></div>}</div></li>})}</ul>:<p className="muted">No supporting documents added.</p>}
  </section>;
}
