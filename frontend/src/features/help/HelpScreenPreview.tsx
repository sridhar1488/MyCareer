export type ScreenPreviewData = {
  page_title: string;
  nav_items: string[];
  eyebrow: string;
  status: string;
  details: string[];
  action: string;
};

export function HelpScreenPreview({ preview }: { preview: ScreenPreviewData }) {
  return <figure className="help-screen-figure">
    <figcaption>Illustrative screen - sample content</figcaption>
    <div className="help-screen" aria-label={`Illustrative MyCareer ${preview.page_title} screen`}>
      <div className="help-screen-top"><span className="help-screen-brand">MyCareer</span><span>Alex Morgan&nbsp; · &nbsp;Sign out</span></div>
      <div className="help-screen-body">
        <aside className="help-screen-nav" aria-hidden="true">{preview.nav_items.map((item, index) => <span className={index === 0 ? 'selected' : ''} key={item}>{item}</span>)}</aside>
        <div className="help-screen-content">
          <span className="help-screen-eyebrow">{preview.eyebrow}</span>
          <div className="help-screen-heading"><strong>{preview.page_title}</strong><span className="help-screen-status">{preview.status}</span></div>
          <ul>{preview.details.map((detail, index) => <li key={`${detail}-${index}`}>{detail}</li>)}</ul>
          <span className="help-screen-action">{preview.action}</span>
        </div>
      </div>
    </div>
  </figure>;
}
