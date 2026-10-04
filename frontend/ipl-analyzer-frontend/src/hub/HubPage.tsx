import { useEffect } from 'react';
import { ArrowRight } from 'lucide-react';
import '../App.css';
import './HubPage.css';
import PageHeader from '../components/PageHeader';
import SiteHeader from '../components/SiteHeader';
import { isLive, leagueHref, leaguesBySport, statusLabel, type LeagueIndex, type LeagueSummary } from '../data/leagues';
import { formatGeneratedAt } from '../lib/standings';
import { appBaseHref, setJsonLd, setPageMeta } from '../lib/seo';
import { samePageHref } from '../lib/ui';

const TITLE = 'All Live Races: Title, Playoff & Relegation Odds | Playoff Pulse';
const DESCRIPTION =
  "Daily title, playoff and relegation odds for European football from the Premier League to the Süper Lig, the WSL, the Champions League, Europa League and Conference League, MLS and the NWSL, the NFL, NBA, WNBA, NHL and MLB, Australia's A-Leagues, NBL and WNBL, and T20 cricket leagues from the IPL to the Big Bash.";

const LeagueCard = ({ league, index }: { league: LeagueSummary; index: LeagueIndex }) => {
  const status = statusLabel(league);
  return (
    <a className="hub-card" href={leagueHref(league.id, index.default)}>
      <span className="hub-card-top">
        <strong>
          {league.shortName} {league.seasonLabel}
        </strong>
        <small className={`status-pill status-${status.toLowerCase()}`}>{status}</small>
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
        <ArrowRight size={16} aria-hidden="true" />
      </span>
    </a>
  );
};

/** The all-sports home page: every live race first, grouped by sport, then last season's final tables. */
const HubPage = ({ index }: { index: LeagueIndex }) => {
  useEffect(() => {
    const href = appBaseHref();
    setPageMeta(TITLE, DESCRIPTION, `${href}?view=hub`);
    setJsonLd({
      '@context': 'https://schema.org',
      '@type': 'WebSite',
      '@id': `${href}#website`,
      name: 'Playoff Pulse',
      url: href,
      description: DESCRIPTION,
    });
  }, [index.default]);

  const liveLeagues = index.leagues.filter(isLive);
  const live = leaguesBySport({ ...index, leagues: liveLeagues });
  const finished = leaguesBySport({ ...index, leagues: index.leagues.filter((league) => !isLive(league)) });
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
      <main className="pulse-app hub-page" data-testid="hub-page" id="main">
        <PageHeader
          facts={[
            { label: 'Live races', value: liveLeagues.length },
            { label: 'Leagues covered', value: index.leagues.length },
            ...(latest ? [{ label: 'Latest update', value: formatGeneratedAt(latest) }] : []),
          ]}
          factsLabel="Site snapshot"
          strap="Title, playoff and relegation chances for football in Europe, the Americas and Australia, the European cups, the NFL, NBA, WNBA, NHL, MLB and NBL, and T20 cricket, from thousands of simulated seasons and updated daily."
          title="All Live Races"
        />

        {live.length > 0 && (
          <section className="hub-section" aria-labelledby="live-title">
            <div className="section-heading">
              <h2 id="live-title">Live Races</h2>
              <p>Seasons in progress, newest odds first</p>
            </div>
            {live.map((group) => (
              <div className="hub-group" key={group.sport}>
                <h3>{group.label}</h3>
                <div className="hub-grid">
                  {group.leagues.map((league) => (
                    <LeagueCard index={index} key={league.id} league={league} />
                  ))}
                </div>
              </div>
            ))}
          </section>
        )}

        {finished.length > 0 && (
          <section className="panel hub-section" aria-labelledby="final-title">
            <div className="section-heading">
              <h2 id="final-title">Final Tables</h2>
              <p>Completed seasons and their champions</p>
            </div>
            <div className="hub-finished-groups">
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
            </div>
          </section>
        )}
      </main>

      <footer className="pulse-footer">
        <span>Model estimates for fans, not betting advice.</span>
        <span>Sources are credited on each league page.</span>
      </footer>
    </>
  );
};

export default HubPage;
