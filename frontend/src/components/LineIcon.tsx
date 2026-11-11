export function LineIcon({ path }: { path: string }) {
  return <svg aria-hidden="true" focusable="false" className="line-icon" viewBox="0 0 24 24">
    <path d={path} />
  </svg>;
}
