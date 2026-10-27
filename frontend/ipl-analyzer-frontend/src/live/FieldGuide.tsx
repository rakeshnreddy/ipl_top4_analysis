import { useEffect, useState } from 'react';
export default function FieldGuide() {
  const [tilted, setTilted] = useState(false);
  const [reduced, setReduced] = useState(() => typeof window.matchMedia === 'function' && window.matchMedia('(prefers-reduced-motion: reduce)').matches);
  useEffect(() => {
    if (typeof window.matchMedia !== 'function') return;
    const query = window.matchMedia('(prefers-reduced-motion: reduce)');
    const change = () => {
      setReduced(query.matches);
      if (query.matches) setTilted(false);
    };
    query.addEventListener?.('change', change);
    return () => query.removeEventListener?.('change', change);
  }, []);
  return <div className="lc-field-guide">
  <p className="lc-eyebrow">Illustrative · not match tracking</p>
  <h3 className="lc-section-title">A guide to the field</h3>
  <p className="lc-muted">A simplified field for a right-handed batter facing the bowler. Positions change by tactics and the batter's end. This diagram does not depict the selected match.</p>
  <div className="lc-guide-controls" role="group" aria-label="Field view">
    <button type="button" className="lc-button" aria-pressed={!tilted || reduced} onClick={() => setTilted(false)}>Flat view</button>
    <button type="button" className="lc-button" aria-pressed={tilted && !reduced} disabled={reduced} onClick={() => setTilted(true)}>Tilt field</button>
  </div>
  {reduced && <p className="lc-muted">Flat view follows your reduced-motion preference.</p>}
  <div className="lc-field-stage">
    <svg className={`lc-field-svg${tilted && !reduced ? ' is-tilted' : ''}`} role="img" aria-labelledby="lc-field-title lc-field-description" viewBox="0 0 520 360">
      <title id="lc-field-title">Illustrative cricket field and pitch</title>
      <desc id="lc-field-description">An oval boundary surrounds the central pitch. The bowler is above the right-handed batter, with the wicketkeeper below. Off side is on the left, leg side on the right. No player positions or ball trajectories are measured.</desc>
      <ellipse cx="260" cy="180" rx="236" ry="156" className="lc-field-grass" />
      <ellipse cx="260" cy="180" rx="218" ry="140" className="lc-field-line" />
      <ellipse cx="260" cy="180" rx="96" ry="94" className="lc-field-inner" />
      <rect x="246" y="103" width="28" height="146" rx="3" className="lc-pitch" />
      <path d="M238 120h44M238 232h44M255 116v8m5-8v8m5-8v8M255 228v8m5-8v8m5-8v8" className="lc-crease-lines" />
      <circle cx="260" cy="90" r="9" className="lc-bowler" />
      <circle cx="274" cy="220" r="9" className="lc-batter" />
      <circle cx="260" cy="264" r="9" className="lc-keeper" />
    </svg>
  </div>
  <div className="lc-guide-sides">
    <span>Off side · left</span>
    <span>Leg side · right</span>
  </div>
  <dl className="lc-guide-legend">
    <div>
      <dt><i className="lc-bowler-key" />Bowler</dt>
      <dd>Delivers toward the batter.</dd>
    </div>
    <div>
      <dt><i className="lc-batter-key" />Batter</dt>
      <dd>Faces the bowler from the crease.</dd>
    </div>
    <div>
      <dt><i className="lc-keeper-key" />Wicketkeeper</dt>
      <dd>Stands behind the batter's wicket.</dd>
    </div>
  </dl>
  <p className="lc-muted">Tracked field placement, shot paths and ball flight require a verified spatial feed. Scoring commentary alone cannot reconstruct them.</p>
  </div>;
}
