import { useEffect } from 'react';
import { ArrowRight, Trophy, Zap } from 'lucide-react';
import '../App.css';
import './HubPage.css';
import { isLive, leagueHref, leaguesBySport, statusLabel, type LeagueIndex, type LeagueSummary } from '../data/leagues';
import { formatGeneratedAt } from '../lib/standings';
import { appBaseHref, setJsonLd, setPageMeta } from '../lib/seo';

const TITLE = 'Playoff Pulse: Live Title & Playoff Odds for Football, NFL, NBA, NHL, MLB & Cricket';
const DESCRIPTION =
  "Daily title, playoff and relegation odds for Europe's top football leagues, the NFL, NBA, NHL and MLB, and T20 cricket leagues from the IPL to the Big Bash.";

const LeagueCard = ({ league, index }: { league: LeagueSummary; index: LeagueIndex }) => (
  <a className={`hub-card ${isLive(league) ? 'is-live' : ''}`} href={leagueHref(league.id, index.default)}>
    <span className="hub-card-top">
      <strong>
        {league.shortName} {league.seasonLabel}
      </strong>
      <small className={`hub-status status-${statusLabel(league).toLowerCase()}`}>{statusLabel(league)}</small>
    </span>
    {league.name !== league.shortName && <span className="hub-card-name">{league.name}</span>}
    {league.facts && league.facts.length > 0 && (
      <dl>
        {league.facts.map((fact) => (
          <div key={fact.label}>
            <dt>{fact.label}</dt>
            <dd>{fact.value}</dd>
          </div>
        ))}
      </dl>
    )}
    <span className="hub-card-foot">
      Updated {formatGeneratedAt(league.generatedAt)}
      <ArrowRight size={14} aria-hidden="true" />
    </span>
  </a>
);

/** The all-sports home page: every live race first, then last season's final tables. */
const HubPage = ({ index }: { index: LeagueIndex }) => {
  useEffect(() => {
    const href = appBaseHref();
    setPageMeta(TITLE, DESCRIPTION, index.default === 'hub' ? href : `${href}?view=hub`);
    setJsonLd({
      '@context': 'https://schema.org',
      '@type': 'WebSite',
      '@id': `${href}#website`,
      name: 'Playoff Pulse',
      url: href,
      description: DESCRIPTION,
    });
  }, [index.default]);

  const live = index.leagues.filter(isLive);
  const finished = leaguesBySport({ ...index, leagues: index.leagues.filter((league) => !isLive(league)) });

  return (
    <main className="pulse-app hub-page" data-testid="hub-page">
      <section className="hero-band compact-hero" aria-labelledby="page-title">
        <div className="hero-copy hub-hero">
          <div className="hero-main">
            <span className="eyebrow">
              <Zap size={14} aria-hidden="true" />
              Playoff Pulse
            </span>
            <h1 id="page-title">Live Title & Playoff Odds</h1>
            <p>Football, NFL, NBA, NHL, MLB and T20 cricket, from thousands of simulated seasons, updated daily.</p>
          </div>
        </div>
      </section>

      {live.length > 0 && (
        <section className="race-summary-panel" aria-labelledby="live-title">
          <div className="section-heading">
            <div>
              <span className="panel-kicker">In season</span>
              <h2 id="live-title">Live Races</h2>
            </div>
            <Zap aria-hidden="true" />
          </div>
          <div className="hub-grid">
            {live.map((league) => (
              <LeagueCard index={index} key={league.id} league={league} />
            ))}
          </div>
        </section>
      )}

      {finished.length > 0 && (
        <section className="race-summary-panel" aria-labelledby="final-title">
          <div className="section-heading">
            <div>
              <span className="panel-kicker">Completed seasons</span>
              <h2 id="final-title">Final Tables</h2>
            </div>
            <Trophy aria-hidden="true" />
          </div>
          {finished.map((group) => (
            <div className="hub-finished" key={group.sport}>
              <h3>{group.label}</h3>
              <ul>
                {group.leagues.map((league) => (
                  <li key={league.id}>
                    <a href={leagueHref(league.id, index.default)}>
                      <strong>
                        {league.shortName} {league.seasonLabel}
                      </strong>
                      {league.champion && <span>Champions: {league.champion}</span>}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </section>
      )}

      <footer className="pulse-footer">
        <span>Model estimates for fans, not betting advice.</span>
        <span>Sources are credited on each league page.</span>
      </footer>
    </main>
  );
};

export default HubPage;
