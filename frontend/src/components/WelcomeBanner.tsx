export function WelcomeBanner({ name, message }: { name: string; message: string }) {
  return <section className="welcome-panel">
    <div className="welcome-copy">
      <h2>Welcome, {name.trim().split(/\s+/)[0]}.</h2>
      <p>{message}</p>
    </div>
    <div className="growth-art" aria-hidden="true"><span /><span /><span /><span /></div>
  </section>;
}
