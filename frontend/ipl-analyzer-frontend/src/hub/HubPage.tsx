import { useEffect, useRef, useState } from 'react';
import { ArrowRight, Search } from 'lucide-react';
import '../App.css';
import './HubPage.css';
import PageHeader from '../components/PageHeader';
import SiteHeader from '../components/SiteHeader';
import { leagueHref, leaguesBySport, sportName, sportOf, statusLabel, type LeagueIndex, type LeagueSummary } from '../data/leagues';
import { formatGeneratedAt } from '../lib/standings';
import { appBaseHref, setJsonLd, setPageMeta } from '../lib/seo';
import { samePageHref } from '../lib/ui';

const TITLE = 'All Live Races: Title, Playoff & Relegation Odds | Playoff Pulse';
const DESCRIPTION =
  "Title, playoff and relegation odds across football, cricket, basketball, US sports and Formula 1. Find seasons in progress, pre-season projections and final tables, with odds updated twice daily.";

type SeasonState = 'in-season' | 'upcoming' | 'final';
const SEASONS: { key: SeasonState; label: string; heading: string; note: string }[] = [
  { key: 'in-season', label: 'In season', heading: 'In Season', note: 'Current season races · odds refreshed twice daily' },
  { key: 'upcoming', label: 'Upcoming', heading: 'Upcoming Seasons', note: 'Pre-season projections, before the first result' },
  { key: 'final', label: 'Final', heading: 'Final Tables', note: 'Completed seasons and their champions' },
];
const stateOf = (league: LeagueSummary): SeasonState =>
  league.status === 'complete' ? 'final' : league.started === false ? 'upcoming' : 'in-season';
const searchable = (value: string) => value.normalize('NFD').replace(/\p{M}/gu, '').toLowerCase().replace(/[^a-z0-9]/g, '');

const LeagueCard = ({ league, index }: { league: LeagueSummary; index: LeagueIndex }) => {
  const status = statusLabel(league);
  const facts = league.facts ?? [];
  return (
    <a className={`hub-card hub-card-${stateOf(league)}`} href={leagueHref(league.id, index.default)}>
      <h4>{league.shortName}</h4>
      <span className="hub-card-top">
        <span className="hub-card-season">{league.seasonLabel}</span>
        <small className={`status-pill status-${status.toLowerCase()}`}>{status}</small>
      </span>
      {league.name !== league.shortName && <span className="hub-card-name">{league.name}</span>}
      {facts.length > 0 ? (
        <dl>
          {facts.map((fact, position) => (
            <div className={position === 0 ? 'hub-card-headline' : 'hub-card-detail'} key={fact.label}>
              <dt>{fact.label}</dt>
              <dd>{fact.value}</dd>
            </div>
          ))}
        </dl>
      ) : league.champion ? (
        <dl><div className="hub-card-headline"><dt>Champions</dt><dd>{league.champion}</dd></div></dl>
      ) : (
        <p className="hub-card-empty">{stateOf(league) === 'final' ? 'Final standings and results' : 'Standings and season outlook'}</p>
      )}
      <span className="hub-card-foot">
        <span>Updated {formatGeneratedAt(league.generatedAt)}</span>
        <ArrowRight size={16} aria-hidden="true" />
      </span>
    </a>
  );
};

/** Search every published season without conflating upcoming projections with seasons in progress. */
const HubPage = ({ index }: { index: LeagueIndex }) => {
  const [query, setQuery] = useState('');
  const [sport, setSport] = useState('all');
  const [season, setSeason] = useState<SeasonState | 'all'>('all');
  const searchRef = useRef<HTMLInputElement>(null);
  useEffect(() => {
    const href = appBaseHref();
    setPageMeta(TITLE, DESCRIPTION, `${href}?view=hub`);
    setJsonLd({ '@context': 'https://schema.org', '@type': 'WebSite', '@id': `${href}#website`,
      name: 'Playoff Pulse', url: href, description: DESCRIPTION });
  }, [index.default]);

  const sports = leaguesBySport(index);
  const sportLabels = new Map(sports.flatMap((group) => group.leagues.map((league) => [league.id, group.label] as const)));
  const sportMembers = new Set(sports.find((group) => group.sport === sport)?.leagues.map((league) => league.id));
  const counts = Object.fromEntries(SEASONS.map(({ key }) => [key, index.leagues.filter((league) => stateOf(league) === key).length]));
  const needle = searchable(query.trim());
  const matching = index.leagues.filter((league) =>
    (sport === 'all' || sportMembers.has(league.id))
    && (season === 'all' || stateOf(league) === season)
    && (!needle || searchable(`${league.name} ${league.shortName} ${league.id} ${league.seasonLabel} ${sportName(sportOf(league))} ${sportLabels.get(league.id) ?? ''}`).includes(needle)),
  );
  const active = Boolean(query || sport !== 'all' || season !== 'all');
  const clear = () => { setQuery(''); setSport('all'); setSeason('all'); searchRef.current?.focus(); };

  return (
    <>
      <a className="skip-link" href={samePageHref('#main')}>Skip to content</a>
      <SiteHeader index={index} />
      <main className="pulse-app hub-page" data-testid="hub-page" id="main">
        <PageHeader
          facts={[
            { label: 'In season', value: counts['in-season'] },
            { label: 'Upcoming', value: counts.upcoming },
            { label: 'Final', value: counts.final },
            { label: 'Leagues', value: index.leagues.length },
          ]}
          factsLabel="Site snapshot"
          strap="Current, upcoming and final seasons. Odds updated twice daily."
          title="All Live Races"
        />

        <section className="hub-controls" aria-label="Find a league">
          <div className="hub-search-row">
            <div className="hub-search">
              <label htmlFor="hub-league-search">Search leagues</label>
              <div>
                <Search aria-hidden="true" size={18} />
                <input id="hub-league-search" ref={searchRef} type="search" value={query}
                  onChange={(event) => setQuery(event.target.value)} placeholder="League, sport or season…" />
              </div>
            </div>
            <button className="hub-clear" type="button" aria-label="Clear filters" onClick={clear} disabled={!active}>Clear</button>
          </div>
          <fieldset className="hub-filters">
            <legend>Sport</legend>
            <div>
              <button type="button" aria-pressed={sport === 'all'} onClick={() => setSport('all')}>All sports</button>
              {sports.map((group) => (
                <button type="button" key={group.sport} aria-pressed={sport === group.sport} onClick={() => setSport(group.sport)}>
                  {group.label} <span>{group.leagues.length}</span>
                </button>
              ))}
            </div>
          </fieldset>
          <fieldset className="hub-filters">
            <legend>Season</legend>
            <div>
              <button type="button" aria-pressed={season === 'all'} onClick={() => setSeason('all')}>All seasons</button>
              {SEASONS.map(({ key, label }) => (
                <button type="button" key={key} aria-pressed={season === key} onClick={() => setSeason(key)}>
                  {label} <span>{counts[key]}</span>
                </button>
              ))}
            </div>
          </fieldset>
          <p className="hub-result-count" aria-live="polite" aria-atomic="true">
            Showing {matching.length} of {index.leagues.length} leagues
          </p>
        </section>

        {matching.length === 0 && (
          <section className="hub-empty" role="status">
            <h2>{index.leagues.length === 0 ? 'No leagues have been published yet.' : 'No leagues match these filters.'}</h2>
            <p>{index.leagues.length === 0 ? 'Season tables will appear here after the next data update.' : 'Try a shorter name, a different sport or another season state.'}</p>
            {active && <button type="button" onClick={clear}>Show all leagues</button>}
          </section>
        )}

        {SEASONS.map((bucket) => {
          const groups = leaguesBySport({ ...index, leagues: matching.filter((league) => stateOf(league) === bucket.key) });
          return groups.length > 0 && (
            <section className="hub-section" key={bucket.key} aria-labelledby={`hub-${bucket.key}`}>
              <div className="section-heading">
                <h2 id={`hub-${bucket.key}`}>{bucket.heading}</h2>
                <p>{bucket.note}</p>
              </div>
              {groups.map((group) => (
                <div className="hub-group" key={group.sport}>
                  <div className="hub-group-heading"><h3>{group.label}</h3><span>{group.leagues.length} {group.leagues.length === 1 ? 'league' : 'leagues'}</span></div>
                  <div className="hub-grid">
                    {group.leagues.map((league) => <LeagueCard index={index} key={league.id} league={league} />)}
                  </div>
                </div>
              ))}
            </section>
          );
        })}
      </main>
      <footer className="pulse-footer">
        <span>Model estimates for fans, not betting advice.</span>
        <span>Sources are credited on each league page.</span>
      </footer>
    </>
  );
};

export default HubPage;
