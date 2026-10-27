import './SiteFooter.css';

/** General project links; per-page source and licence credits remain beside their data. */
export default function SiteFooter() {
  const base = import.meta.env.BASE_URL;
  return <footer className="site-info-footer">
    <div className="site-info-inner">
      <a className="site-info-brand" href={base}>Playoff Pulse</a>
      <nav aria-label="About Playoff Pulse">
        <a href={`${base}about/`}>About</a>
        <a href={`${base}methodology/`}>Methodology</a>
        <a href={`${base}privacy/`}>Privacy</a>
        <a href={`${base}advertise/`}>Advertise</a>
      </nav>
      <p>Independent sports analysis. Recorded results, model estimates and external prices have different meanings.</p>
    </div>
  </footer>;
}
