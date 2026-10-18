import { AlertTriangle } from 'lucide-react';

/** Shown while the league list or a league's data loads. */
export const LoadingState = () => (
  <main className="pulse-app pulse-center loading-shell" id="main">
    <div className="loading-panel" role="status" aria-live="polite">
      <span aria-hidden="true" className="spinner" />
      <span>Loading Playoff Pulse…</span>
    </div>
    <div aria-hidden="true" className="skeleton-shell">
      <div className="skeleton-heading" />
      <div className="skeleton-table">{Array.from({ length: 7 }, (_, i) => <div className="skeleton-row" key={i} />)}</div>
    </div>
  </main>
);

/** A page whose data failed to load, with a way back to the home page. */
export const ErrorState = ({ title, message, homeHref, onRetry }: { title: string; message: string; homeHref?: string; onRetry?: () => void }) => (
  <main className="pulse-app pulse-center" id="main">
    <section className="error-panel" role="alert">
      <AlertTriangle aria-hidden="true" />
      <h1>{title}</h1>
      <p>{message}</p>
      {onRetry && <button onClick={onRetry} type="button">Reload this page</button>}
      {homeHref && <a href={homeHref}>Go to the home page</a>}
    </section>
  </main>
);
