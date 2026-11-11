import {useEffect,useState} from 'react';
import {markUnsaved} from '../../app/unsaved';
import {api} from '../../api/client';
import {useApi} from '../../api/useApi';
import type {components} from '../../api/schema';
import {Feedback} from '../../components/Feedback';
import {Pagination} from '../../components/Pagination';
import {appraisalHeaderLimit,appraisalResponseLimit,appraisalTextMinimum} from '../../utils/appraisalTextLimits';
import {TextSections,type Config} from './config';
type Template=components['schemas']['TemplateResponse'];
export function FormBuilder(){
 const [revision,refresh]=useState(0),[page,setPage]=useState(1),[draft,setDraft]=useState<Template|null>(null),[config,setConfig]=useState<Config|null>(null),[error,setError]=useState(''),[busy,setBusy]=useState(false),[dirty,setDirty]=useState(false),[preview,setPreview]=useState(false);
 useEffect(()=>{markUnsaved(dirty);return()=>markUnsaved(false);},[dirty]);
 useEffect(()=>{const handler=(e:BeforeUnloadEvent)=>{if(dirty){e.preventDefault();e.returnValue='';}};window.addEventListener('beforeunload',handler);return()=>window.removeEventListener('beforeunload',handler);},[dirty]);
 const {data,error:loadError,loading}=useApi<components['schemas']['TemplatePage']>(`/hr/forms?page=${page}`,revision);
 async function create(){setError('');try{setDraft(null);setConfig(await api('/hr/forms/default'));setDirty(true);}catch(e){setError((e as Error).message);}}
 function change(v:Config){setConfig(v);setDirty(true);}
 async function save(publish=false){if(!config)return;setBusy(true);setError('');try{let current=draft;if(dirty || !current){current=await api<Template>(current?`/hr/forms/${current.id}`:'/hr/forms',current?'PUT':'POST',current?{expected_version:current.version,config}:config);setDraft(current);setDirty(false);}if(publish){current=await api<Template>(`/hr/forms/${current.id}/publish`,'POST',{expected_version:current.version});setDraft(current);}refresh(revision+1);}catch(e){setError((e as Error).message);}finally{setBusy(false);}}
 function close(){if(!dirty||window.confirm('Discard unsaved form changes?')){setConfig(null);setDraft(null);setPreview(false);setDirty(false);}}
 if (!config) return <>
  {(error || loadError) && <Feedback message={error || loadError} />}
  <section className="panel form-builder-list">
   <div className="section-heading">
    <p className="muted section-intro">Publish forms for future appraisal cycles. Active cycles retain their original form and scoring rules.</p>
    <button className="button primary" onClick={create}>Create form</button>
   </div>
   {loading && <p role="status">Loading forms…</p>}
   {data && <>
    {data.items.length > 0 && <div className="table-scroll">
     <table aria-label="Appraisal forms">
      <thead><tr><th scope="col">Form</th><th scope="col">Publication status</th><th scope="col">Actions</th></tr></thead>
      <tbody>{data.items.map(form => <tr key={form.id}>
       <td><strong>{form.config.name}</strong><small>Draft version {form.version}</small></td>
       <td>{form.published_form_id
        ? <span className="status active">Published version available</span>
        : <span className="status">Not published</span>}</td>
       <td><button className="text-button" aria-label={`Edit form ${form.config.name}`} onClick={() => {
        setDraft(form); setConfig(form.config); setDirty(false);
       }}>Edit form</button></td>
      </tr>)}</tbody>
     </table>
    </div>}
    {data.total === 0 && <p className="muted section-intro">No appraisal forms yet. Create a form to get started.</p>}
    {data.total > 0 && data.items.length === 0 && <p className="muted section-intro">No forms on this page.</p>}
    {(page > 1 || data.total > data.page_size) && <Pagination page={page} total={data.total} size={data.page_size} onPage={setPage} />}
   </>}
  </section>
 </>;
 const core=['goals','contributions','competencies','development'] as const;
 const titleLength=config.goal_title_max_length ?? appraisalHeaderLimit;
 const descriptionLength=config.goal_description_max_length ?? appraisalResponseLimit;
 return <><div className="action-bar"><button className="button" disabled={busy} onClick={close}>Back to forms</button><button className="button" onClick={()=>setPreview(!preview)}>{preview?'Edit fields':'Preview form'}</button></div>{error&&<Feedback message={error}/>}<p>Manager ratings remain whole numbers from 1–5. Goals and manager strengths/improvements remain part of every form. Disabled rated sections must have zero weight; weights must total 100%.</p>{preview?<section className="panel"><h2>{config.name}</h2>{config.section_order?.map(id=>{const section=config.text_sections?.find(s=>s.id===id);if(section)return <TextSections key={id} config={config} owner={section.owner} sectionId={id} answers={{}}/>;if(id==='goals')return <p key={id}>{config.goals_title} · up to {config.goals_limit} goals · {config.weights!.goals}%</p>;if(id==='contributions'&&config.contributions_enabled)return <p key={id}>{config.contributions_title} · up to {config.contributions_limit} · {config.weights!.contributions}%</p>;if(id==='competencies'&&config.competencies_enabled)return <div key={id}><h3>{config.competencies_title} · {config.weights!.competencies}%</h3>{config.competencies.map(c=><p key={c.id}>{c.label}{c.leadership?' (N/A allowed with reason)':''}</p>)}</div>;if(id==='development'&&config.development_enabled)return <p key={id}>{config.development_title} · Workbook development questions</p>;return null;})}<p>Manager strengths and improvements</p></section>:<>
 <section className="panel"><label htmlFor="form-name">Form name</label><input id="form-name" maxLength={150} value={config.name} onChange={e=>change({...config,name:e.target.value})}/>{core.map(key=><div key={key}><label htmlFor={`title-${key}`}>{key} section title</label><input id={`title-${key}`} maxLength={150} value={config[`${key}_title`]} onChange={e=>change({...config,[`${key}_title`]:e.target.value})}/>{key!=='goals'&&<label className="choice"><input type="checkbox" checked={config[`${key}_enabled`]} onChange={e=>change({...config,[`${key}_enabled`]:e.target.checked,...(!e.target.checked&&key!=='development'?{weights:{...config.weights!,[key]:0}}:{})})}/>Include this section</label>}{key!=='development'&&<><label htmlFor={`weight-${key}`}>Section weight (%)</label><input id={`weight-${key}`} type="number" min={0} max={100} value={config.weights![key]} onChange={e=>change({...config,weights:{...config.weights!,[key]:Number(e.target.value)}})}/></>}{(key==='goals'||key==='contributions')&&<><label htmlFor={`limit-${key}`}>Maximum entries</label><input id={`limit-${key}`} type="number" min={1} max={100} value={config[`${key}_limit`]} onChange={e=>change({...config,[`${key}_limit`]:Number(e.target.value)})}/></>}</div>)}</section>
 <section className="panel"><h2>Goal character limits</h2>
  <p className="muted">You can set lower limits for cycles that use this form. Goal titles allow up to {appraisalHeaderLimit} characters and achievement descriptions allow up to {appraisalResponseLimit}.</p>
  <div className="form-grid">
   <label>Goal title character limit<input type="number" min={appraisalTextMinimum} max={appraisalHeaderLimit} value={titleLength || ''} onChange={e=>change({...config,goal_title_max_length:Number(e.target.value)})}/></label>
   <label>Goal achievement description character limit<input type="number" min={appraisalTextMinimum} max={appraisalResponseLimit} value={descriptionLength || ''} onChange={e=>change({...config,goal_description_max_length:Number(e.target.value)})}/></label>
  </div>
 </section>
 <section className="panel"><h2>Competencies</h2>{config.competencies.map((c,i)=><div key={c.id}><label htmlFor={`comp-${c.id}`}>Competency {i+1}</label><input id={`comp-${c.id}`} maxLength={150} value={c.label} onChange={e=>change({...config,competencies:config.competencies.map((v,n)=>n===i?{...v,label:e.target.value}:v)})}/><label className="choice"><input type="checkbox" checked={c.leadership??false} onChange={e=>change({...config,competencies:config.competencies.map((v,n)=>({...v,leadership:n===i?e.target.checked:false}))})}/>Leadership: N/A allowed with a reason</label><button className="button small" disabled={config.competencies.length<=1} onClick={()=>change({...config,competencies:config.competencies.filter((_,n)=>n!==i)})}>Remove competency {i+1}</button></div>)}<button className="button" disabled={config.competencies.length>=50} onClick={()=>change({...config,competencies:[...config.competencies,{id:crypto.randomUUID(),label:'New competency',leadership:false}]})}>Add competency</button></section>
 <section className="panel"><h2>Custom text sections</h2>{config.text_sections?.map((s,i)=><fieldset key={s.id}><legend>Custom section {i+1}</legend><label htmlFor={`section-${s.id}`}>Section title</label><input id={`section-${s.id}`} maxLength={150} value={s.title} onChange={e=>change({...config,text_sections:config.text_sections?.map((v,n)=>n===i?{...v,title:e.target.value}:v)})}/><label htmlFor={`owner-${s.id}`}>Completed by</label><select id={`owner-${s.id}`} value={s.owner} onChange={e=>change({...config,text_sections:config.text_sections?.map((v,n)=>n===i?{...v,owner:e.target.value as 'EMPLOYEE'|'MANAGER'}:v)})}><option value="EMPLOYEE">Employee</option><option value="MANAGER">Manager</option></select>{s.questions.map((q,j)=><div key={q.id}><label htmlFor={`label-${q.id}`}>Question {j+1}</label><input id={`label-${q.id}`} maxLength={500} value={q.label} onChange={e=>change({...config,text_sections:config.text_sections?.map((v,n)=>n===i?{...v,questions:v.questions.map((a,k)=>k===j?{...a,label:e.target.value}:a)}:v)})}/><label className="choice"><input type="checkbox" checked={q.required??false} onChange={e=>change({...config,text_sections:config.text_sections?.map((v,n)=>n===i?{...v,questions:v.questions.map((a,k)=>k===j?{...a,required:e.target.checked}:a)}:v)})}/>Required before submission / finalization</label><button className="button small" disabled={s.questions.length<=1} onClick={()=>change({...config,text_sections:config.text_sections?.map((v,n)=>n===i?{...v,questions:v.questions.filter((_,k)=>k!==j)}:v)})}>Remove question</button></div>)}<button className="button" onClick={()=>change({...config,text_sections:config.text_sections?.map((v,n)=>n===i?{...v,questions:[...v.questions,{id:crypto.randomUUID(),label:'New question',required:false}]}:v)})}>Add question</button><button className="button" onClick={()=>change({...config,text_sections:config.text_sections?.filter((_,n)=>n!==i),section_order:config.section_order?.filter(id=>id!==s.id)})}>Remove section</button></fieldset>)}<button className="button" disabled={(config.text_sections?.length??0)>=20} onClick={()=>{const id=crypto.randomUUID();change({...config,text_sections:[...(config.text_sections??[]),{id,title:'New section',owner:'EMPLOYEE',questions:[{id:crypto.randomUUID(),label:'New question',required:false}]}],section_order:[...(config.section_order??[]),id]});}}>Add text section</button></section>
 <section className="panel"><h2>Section order</h2>{config.section_order?.map((id,i)=><div className="action-bar" key={id}><span>{core.includes(id as typeof core[number])?config[`${id as typeof core[number]}_title`]:config.text_sections?.find(s=>s.id===id)?.title}</span>{[-1,1].map(direction=><button className="button small" key={direction} disabled={i+direction<0||i+direction>=(config.section_order?.length??0)} onClick={()=>{const order=[...(config.section_order??[])];[order[i],order[i+direction]]=[order[i+direction],order[i]];change({...config,section_order:order});}}>{direction<0?'Move up':'Move down'}</button>)}</div>)}</section></>}
 <div className="panel action-bar"><button className="button" disabled={busy||(!dirty&&!!draft)} onClick={()=>save()}>Save form draft</button><button className="button primary" disabled={busy} onClick={()=>{if(window.confirm('Publish an immutable version for future cycles? Unsaved changes will be saved first.'))save(true);}}>Publish form version</button>{draft?.published_form_id&&<span role="status">Published version available for cycle selection.</span>}</div></>;
}
