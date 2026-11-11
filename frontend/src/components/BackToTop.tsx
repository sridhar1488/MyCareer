import type { RefObject } from 'react';

export function BackToTop({ target }: { target: RefObject<HTMLButtonElement | null> }) {
  function goToTop() {
    target.current?.focus({ preventScroll: true });
    target.current?.scrollIntoView({ block: 'start' });
  }

  return <div className="action-bar">
    <button className="button" type="button" onClick={goToTop}>
      <span aria-hidden="true">↑ </span>Back to top
    </button>
  </div>;
}
