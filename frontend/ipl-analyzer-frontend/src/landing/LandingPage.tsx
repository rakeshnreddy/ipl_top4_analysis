import { useEffect } from 'react';
import { ArrowRight } from 'lucide-react';
import '../App.css';
import './LandingPage.css';
import SiteHeader from '../components/SiteHeader';
import { hubHref, isLive, leagueHref, leaguesBySport, statusLabel, type LeagueIndex } from '../data/leagues';
import { formatGeneratedAt } from '../lib/standings';
import { appBaseHref, setJsonLd, setPageMeta } from '../lib/seo';
import { samePageHref } from '../lib/ui';

const TITLE = 'Playoff Pulse: Live Title, Playoff & Relegation Odds Across Sports';
const DESCRIPTION =
  'Live odds for every title race, playoff chase and relegation fight: European football and the Champions League, MLS, the NFL, NBA, NHL and MLB, Formula 1, T20 cricket and more, from tens of thousands of simulated seasons, updated twice a day.';
const FEATURED = 6;

/** "Football, cricket and basketball" from the sport groups that have leagues. */
function sportList(labels: string[]) {
  const names = labels.map((label) => (label === 'US sports' ? 'American sports' : label.toLowerCase()));
  return names.length > 1 ? `${names.slice(0, -1).join(', ')} and ${names[names.length - 1]}` : (names[0] ?? '');
}

/**
 * The front door: what the site does, the biggest races right now, every league by sport,
 * and how the numbers are made. The hub (?view=hub) is the full list of live races.
 */
const LandingPage = ({ index }: { index: LeagueIndex }) => {
  useEffect(() => {
    const href = appBaseHref();
    setPageMeta(TITLE, DESCRIPTION, href);
    setJsonLd({
      '@context': 'https://schema.org',
      '@type': 'WebSite',
      '@id': `${href}#website`,
      name: 'Playoff Pulse',
      url: href,
      description: DESCRIPTION,
    });
  }, []);

  const live = index.leagues.filter(isLive);
  // The list is already in-season first, then by priority: the first live races with headline odds lead.
  const featured = live.filter((league) => league.facts && league.facts.length > 0).slice(0, FEATURED);
  const groups = leaguesBySport(index).sort((a, b) => b.leagues.filter(isLive).length - a.leagues.filter(isLive).length);
  const latest = index.leagues.reduce<string | null>(
    (newest, league) => (!newest || Date.parse(league.generatedAt) > Date.parse(newest) ? league.generatedAt : newest),
    null,
  );

  return (
    <>
      <a className="skip-link" href={samePageHref('#main')}>
        Skip to content
      </a>
      <SiteHeader index={index} />
      <main className="landing" data-testid="landing-page" id="main">
        <section className="landing-hero" aria-labelledby="landing-title">
          <div className="landing-hero-text">
            <h1 id="landing-title">Every title race, playoff chase and relegation fight, in odds.</h1>
            <p className="landing-lede">
              The rest of every season, played out tens of thousands of times: {index.leagues.length} leagues across{' '}
              {sportList(groups.map((group) => group.label))}, updated twice a day.
            </p>
            <div className="landing-actions">
              <a className="button-primary" href={hubHref()}>
                See all {live.length} live races
                <ArrowRight aria-hidden="true" size={18} />
              </a>
              <a className="landing-text-link" href={samePageHref('#method')}>
                How the odds are made
              </a>
            </div>
            {latest && <p className="landing-updated">Last updated {formatGeneratedAt(latest)}</p>}
          </div>

          {featured.length > 0 && (
            <section className="landing-races" aria-labelledby="races-title">
              <h2 className="label" id="races-title">
                Biggest races right now
              </h2>
              <ol>
                {featured.map((league) => {
                  const status = statusLabel(league);
                  const fact = league.facts?.[0];
                  return (
                    <li key={league.id}>
                      <a href={leagueHref(league.id)}>
                        <span className="landing-race-name">
                          <strong>{league.shortName}</strong>
                          <small className={`status-pill status-${status.toLowerCase()}`}>{status}</small>
                        </span>
                        {fact && (
                          <span className="landing-race-fact">
                            <span>{fact.label}</span>
                            <strong>{fact.value}</strong>
                          </span>
                        )}
                      </a>
                    </li>
                  );
                })}
              </ol>
            </section>
          )}
        </section>

        <section className="landing-sports" aria-labelledby="sports-title">
          <div className="section-heading">
            <h2 id="sports-title">Every League, by Sport</h2>
            <p>
              {live.length} in season now, {index.leagues.length - live.length} with last season's final table
            </p>
          </div>
          <div className="landing-sport-grid">
            {groups.map((group) => {
              const liveCount = group.leagues.filter(isLive).length;
              return (
                <section className="panel landing-sport" key={group.sport} aria-labelledby={`sport-${group.sport}`}>
                  <div className="landing-sport-head">
                    <h3 id={`sport-${group.sport}`}>{group.label}</h3>
                    <span>{liveCount > 0 ? `${liveCount} live` : 'Off-season'}</span>
                  </div>
                  <ul>
                    {group.leagues.map((league) => {
                      const status = statusLabel(league);
                      return (
                        <li key={league.id}>
                          <a href={leagueHref(league.id)}>
                            <span>
                              {league.shortName} <span className="landing-season">{league.seasonLabel}</span>
                            </span>
                            <small className={`status-text status-${status.toLowerCase()}`}>{status}</small>
                          </a>
                        </li>
                      );
                    })}
                  </ul>
                </section>
              );
            })}
          </div>
        </section>

        <section className="panel landing-method" id="method" aria-labelledby="method-title">
          <div className="landing-method-intro">
            <h2 id="method-title">How the Odds Are Made</h2>
            <p>
              No opinions and no bookmaker lines: each page starts from the official results and runs the rest of the season
              forward, game by game.
            </p>
          </div>
          <dl className="landing-method-steps">
            <div>
              <dt>Results from open sources</dt>
              <dd>
                Fixtures and results come from public feeds (FixtureDownload, UEFA, CricketData, Cricsheet, the leagues' own
                services), refreshed every morning and evening. Every table is checked against the league's official one.
              </dd>
            </div>
            <div>
              <dt>Ratings from every result</dt>
              <dd>
                A model rates each team from its recent results, with more weight on the latest. Its settings were chosen by
                replaying past seasons and scoring the predictions against what happened.
              </dd>
            </div>
            <div>
              <dt>The season, played out</dt>
              <dd>
                The remaining games are simulated tens of thousands of times with the league's own points, tiebreakers and
                playoff bracket. The share of seasons a team wins the title is its title chance.
              </dd>
            </div>
            <div>
              <dt>Odds that move with the results</dt>
              <dd>
                After each round the pages show who rose and fell, and which upcoming games swing a race the most.
              </dd>
            </div>
          </dl>
        </section>
      </main>

      <footer className="pulse-footer">
        <span>Model estimates for fans, not betting advice.</span>
        <span>Sources are credited on each league page.</span>
      </footer>
    </>
  );
};

export default LandingPage;
