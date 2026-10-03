import { AlertTriangle } from 'lucide-react';

/** Shown while the league list or a league's data loads. */
export const LoadingState = () => (
  <main className="pulse-app pulse-center" id="main">
    <div className="loading-panel" role="status" aria-live="polite">
      <span aria-hidden="true" className="spinner" />
      <span>Loading Playoff Pulse…</span>
    </div>
  </main>
);

/** A page whose data failed to load, with a way back to the home page. */
export const ErrorState = ({ title, message, homeHref }: { title: string; message: string; homeHref?: string }) => (
  <main className="pulse-app pulse-center" id="main">
    <section className="error-panel" role="alert">
      <AlertTriangle aria-hidden="true" />
      <h1>{title}</h1>
      <p>{message}</p>
      {homeHref && <a href={homeHref}>Go to the home page</a>}
    </section>
  </main>
);
