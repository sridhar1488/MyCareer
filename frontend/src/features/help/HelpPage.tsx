import { useMemo, useState } from 'react';
import { useApi } from '../../api/useApi';
import { Feedback } from '../../components/Feedback';
import { HelpScreenPreview, type ScreenPreviewData } from './HelpScreenPreview';

type HelpStep = { title: string; description: string; bullets: string[]; screenshot: ScreenPreviewData };
type HelpFAQ = { question: string; answer: string };
type HelpGuide = { audience: string; title: string; summary: string; steps: HelpStep[]; faqs: HelpFAQ[] };
type HelpContent = { guides: HelpGuide[] };

export function HelpPage() {
  const [revision, setRevision] = useState(0);
  const [query, setQuery] = useState('');
  const { data, error, loading } = useApi<HelpContent>('/help/content', revision);
  const guides = useMemo(() => {
    const search = query.trim().toLocaleLowerCase();
    if (!search) return data?.guides ?? [];
    return (data?.guides ?? []).map(guide => {
      if (`${guide.title} ${guide.summary}`.toLocaleLowerCase().includes(search)) return guide;
      return {
        ...guide,
        steps: guide.steps.filter(step => [step.title, step.description, ...step.bullets].join(' ').toLocaleLowerCase().includes(search)),
        faqs: guide.faqs.filter(faq => `${faq.question} ${faq.answer}`.toLocaleLowerCase().includes(search)),
      };
    }).filter(guide => guide.steps.length > 0 || guide.faqs.length > 0);
  }, [data, query]);

  return <div className="help-page">
    <section className="panel help-intro">
      <div><span className="eyebrow">MYCAREER SUPPORT</span><h2>How can we help?</h2><p>Follow a role-based walkthrough or search common questions. You only see guides for the tasks your account can perform.</p></div>
      <label className="help-search"><span>Search help topics</span><input value={query} onChange={event => setQuery(event.target.value)} placeholder="Try: deadline, attachment, calibration" /></label>
    </section>
    {loading && <p role="status">Loading help guides…</p>}
    {error && <><Feedback message={error} /><button className="button" onClick={() => setRevision(value => value + 1)}>Try again</button></>}
    {guides.map((guide, guideIndex) => <section className="panel help-guide" key={guide.title}>
      <div className="help-guide-heading"><div><span className="help-audience">{guide.audience}</span><h2>{guide.title}</h2><p className="muted">{guide.summary}</p></div><span className="help-guide-count">{guide.steps.length} steps</span></div>
      {guide.steps.length > 0 && <div className="help-steps"><h3>Walkthrough</h3>{guide.steps.map((step, index) => <details className="help-step" open={index === 0} key={step.title}>
        <summary><span className="help-step-number">{index + 1}</span><span>{step.title}</span></summary>
        <div className="help-step-content"><div><p>{step.description}</p><ul>{step.bullets.map(bullet => <li key={bullet}>{bullet}</li>)}</ul></div><HelpScreenPreview preview={step.screenshot} /></div>
      </details>)}</div>}
      {guide.faqs.length > 0 && <div className="help-faq"><h3>Frequently asked questions</h3>{guide.faqs.map(faq => <details key={faq.question}><summary>{faq.question}</summary><p>{faq.answer}</p></details>)}</div>}
      {guide.steps.length === 0 && guide.faqs.length === 0 && <p className="muted">No matching topics in this guide.</p>}
      {guideIndex === 0 && <p className="help-contact">Still need help? Contact your MyCareer administrator or manager.</p>}
    </section>)}
    {!loading && !error && guides.length === 0 && <section className="panel"><p>No help topics match that search. Try another word or clear the search.</p><button className="button" onClick={() => setQuery('')}>Clear search</button></section>}
    <p className="help-note">Screen previews use fictional sample information for guidance.</p>
  </div>;
}
