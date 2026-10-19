import { useEffect, useState } from 'react';
import { ArrowRight, ChevronDown } from 'lucide-react';
import '../App.css';
import './LandingPage.css';
import SiteHeader from '../components/SiteHeader';
import { hubHref, isLive, leagueHref, leaguesBySport, sportName, sportOf, statusLabel, type LeagueIndex, type LeagueSummary } from '../data/leagues';
import { loadSportData, type SportPayload } from '../data/sportData';
import { formatChance } from '../sport/format';
import { formatGeneratedAt } from '../lib/standings';
import { appBaseHref, setJsonLd, setPageMeta } from '../lib/seo';
import { samePageHref } from '../lib/ui';

const TITLE = 'Playoff Pulse: Live Title, Playoff & Relegation Odds Across Sports';
const DESCRIPTION = 'Title races, playoff chases and relegation fights across football, cricket, basketball, American sports and Formula 1. Explore model season odds, standings and the games that matter, refreshed twice a day.';

interface RacePreview {
  id: string;
  generatedAt: string;
  simulations: number;
  teams: { key: string; name: string; chance: number; color: string }[];
}

/** The preview uses structured numerical output, never parsed index fact strings. */
function titlePreview(payload: SportPayload): RacePreview | null {
  const tier = payload.league.tiers.find((item) => item.key === 'title' || (item.kind === 'top' && item.size === 1));
  if (!tier || tier.settled || payload.metadata.season_status === 'complete') {
    return null;
  }
  const teams = payload.standings.flatMap((row) => {
    const chance = payload.analysis.probabilities[row.teamKey]?.[tier.key];
    const meta = payload.league.teams.find((team) => team.key === row.teamKey);
    return typeof chance === 'number' && Number.isFinite(chance) && chance >= 0 && chance <= 100
      ? [{ key: row.teamKey, name: row.fullName, chance, color: meta?.color ?? 'currentColor' }]
      : [];
  }).sort((a, b) => b.chance - a.chance).slice(0, 4);
  return teams.length ? {
    id: payload.league.id,
    generatedAt: payload.metadata.generated_at,
    simulations: payload.analysis.simulations,
    teams,
  } : null;
}

/** Give each sport a place before featuring more leagues from the same sport. */
function featuredLeagues(index: LeagueIndex) {
  const queues = leaguesBySport(index).map((group) => group.leagues.filter((league) => isLive(league) && league.facts?.length));
  const featured: LeagueSummary[] = [];
  for (let round = 0; featured.length < 6 && queues.some((queue) => queue[round]); round += 1) {
    for (const queue of queues) {
      if (queue[round] && featured.length < 6) {
        featured.push(queue[round]);
      }
    }
  }
  return featured;
}

const RaceFeature = ({ league, preview }: { league: LeagueSummary | undefined; preview: RacePreview | null }) => {
  if (!league) {
    return null;
  }
  const leader = preview?.teams[0];
  return (
    <section className="landing-feature" aria-labelledby="feature-title">
      <div className="landing-feature-top">
        <span className="landing-eyebrow">{sportName(sportOf(league))} · {league.seasonLabel}</span>
        <span className={`status-pill status-${statusLabel(league).toLowerCase()}`}>{statusLabel(league)}</span>
      </div>
      <h2 id="feature-title">{league.shortName}</h2>
      {leader && preview ? (
        <div className="landing-feature-body">
          <div className="landing-favourite">
            <div>
              <span className="landing-team-name"><i aria-hidden="true" style={{ backgroundColor: leader.color }} />{leader.name}</span>
              <span className="landing-feature-label">to win the title</span>
            </div>
            <strong>{formatChance(leader.chance)}</strong>
          </div>
          <div className="landing-feature-track" aria-hidden="true"><span style={{ width: `${leader.chance}%` }} /></div>
          <ol className="landing-contenders" aria-label="Other title chances">
            {preview.teams.slice(1).map((team) => (
              <li key={team.key}>
                <span className="landing-team-name"><i aria-hidden="true" style={{ backgroundColor: team.color }} />{team.name}</span>
                <strong>{formatChance(team.chance)}</strong>
                <span className="landing-contender-track" aria-hidden="true"><span style={{ width: `${team.chance}%` }} /></span>
              </li>
            ))}
          </ol>
          <p className="landing-feature-note">Title chances · 0–100% scale<br />{preview.simulations.toLocaleString()} simulated seasons · {formatGeneratedAt(preview.generatedAt)}</p>
        </div>
      ) : (
        <div className="landing-feature-body landing-feature-fallback">
          <p>{league.champion ? `${league.champion} are champions.` : 'The standings, the season odds and the next games that matter.'}</p>
          {league.facts?.slice(0, 2).map((fact) => (
            <div key={fact.label}><span>{fact.label}</span><strong>{fact.value}</strong></div>
          ))}
        </div>
      )}
      <a className="landing-feature-link" href={leagueHref(league.id)}>
        {leader ? 'Explore the title race' : 'Explore this season'}<ArrowRight aria-hidden="true" size={20} />
      </a>
    </section>
  );
};

const SportDirectory = ({ group }: { group: ReturnType<typeof leaguesBySport>[number] }) => {
  const [expanded, setExpanded] = useState(false);
  const id = `directory-${group.label.toLowerCase().replace(/ /g, '-')}`;
  return (
    <section className="landing-sport">
      <h3>
        <button aria-expanded={expanded} aria-controls={id} onClick={() => setExpanded(!expanded)} type="button">
          <span>{group.label}<small>{group.leagues.length} {group.leagues.length === 1 ? 'league' : 'leagues'}</small></span><ChevronDown aria-hidden="true" size={22} />
        </button>
      </h3>
      <ul hidden={!expanded} id={id}>
        {group.leagues.map((league) => {
          const status = statusLabel(league);
          return (
            <li key={league.id}>
              <a href={leagueHref(league.id)}>
                <span>{league.shortName} <small>{league.seasonLabel}</small></span>
                <small className={`status-text status-${status.toLowerCase()}`}>{status}</small>
              </a>
            </li>
          );
        })}
      </ul>
    </section>
  );
};

const LandingPage = ({ index }: { index: LeagueIndex }) => {
  const active = index.leagues.filter(isLive);
  const ongoing = active.filter((league) => league.started !== false);
  const upcoming = active.length - ongoing.length;
  const sportCount = new Set(index.leagues.map(sportOf)).size;
  const groups = leaguesBySport(index);
  const featured = featuredLeagues(index);
  const featureLeague = ongoing.find((league) => league.id.startsWith('epl-'))
    ?? ongoing.find((league) => sportOf(league) === 'football') ?? active[0] ?? index.leagues[0];
  const [race, setRace] = useState<RacePreview | null>(null);
  const preview = race?.id === featureLeague?.id ? race : null;
  const latest = index.leagues.reduce<string | null>(
    (newest, league) => (!newest || Date.parse(league.generatedAt) > Date.parse(newest) ? league.generatedAt : newest), null,
  );

  useEffect(() => {
    const href = appBaseHref();
    setPageMeta(TITLE, DESCRIPTION, href);
    setJsonLd({ '@context': 'https://schema.org', '@type': 'WebSite', '@id': `${href}#website`, name: 'Playoff Pulse', url: href, description: DESCRIPTION });
  }, []);

  useEffect(() => {
    if (!featureLeague || sportOf(featureLeague) !== 'football' || !isLive(featureLeague)) {
      return;
    }
    let activeRequest = true;
    loadSportData(fetch, featureLeague.id).then((payload) => {
      if (activeRequest) {
        setRace(titlePreview(payload));
      }
    }).catch(() => undefined);
    return () => { activeRequest = false; };
  }, [featureLeague]);

  return (
    <>
      <a className="skip-link" href={samePageHref('#main')}>Skip to content</a>
      <SiteHeader index={index} />
      <main className="landing" data-testid="landing-page" id="main">
        <section className="landing-hero" aria-labelledby="landing-title">
          <div className="landing-hero-inner">
            <div className="landing-hero-text">
              <p className="landing-eyebrow">Title · Playoffs · Relegation</p>
              <h1 id="landing-title">Every race.<br /><span>In the balance.</span></h1>
              <p className="landing-lede">Title races. Playoff chases. See the odds of what comes next.</p>
              <div className="landing-actions">
                <a className="button-primary" href={hubHref()}>Explore the races<ArrowRight aria-hidden="true" size={20} /></a>
                <a className="landing-text-link" href={samePageHref('#method')}>How the odds are made</a>
              </div>
              <p className="landing-coverage">{index.leagues.length} leagues. {sportCount} sports. Refreshed twice a day.</p>
            </div>
            <RaceFeature league={featureLeague} preview={preview} />
          </div>
        </section>

        <section className="landing-section landing-races" aria-labelledby="races-title">
          <div className="landing-section-heading">
            <h2 id="races-title">Featured races</h2>
            <p>{ongoing.length} seasons in progress{upcoming > 0 ? ` · ${upcoming} upcoming` : ''}</p>
          </div>
          {featured.length > 0 ? (
            <ul className="landing-race-grid">
              {featured.map((league) => (
                <li key={league.id}>
                  <a className="landing-race" href={leagueHref(league.id)}>
                    <span className="landing-race-sport">{sportName(sportOf(league))}<span className={`status-text status-${statusLabel(league).toLowerCase()}`}>{statusLabel(league)}</span></span>
                    <h3>{league.shortName}</h3>
                    <span className="landing-race-label">{league.facts?.[0].label}</span>
                    <strong>{league.facts?.[0].value}</strong>
                    <ArrowRight aria-hidden="true" size={20} />
                  </a>
                </li>
              ))}
            </ul>
          ) : <p className="landing-empty">The next season is on its way. Explore the final tables below.</p>}
          {latest && <p className="landing-updated">Latest data update {formatGeneratedAt(latest)}. Season odds, rather than live scores.</p>}
        </section>

        <section className="landing-section landing-directory" aria-labelledby="sports-title">
          <div className="landing-section-heading">
            <div><h2 id="sports-title">Find your league.</h2><p>From the first fixture to the final table.</p></div>
            <a className="landing-text-link" href={hubHref()}>Open the all-sports hub<ArrowRight aria-hidden="true" size={18} /></a>
          </div>
          <div className="landing-directory-list">{groups.map((group) => <SportDirectory group={group} key={group.sport} />)}</div>
        </section>

        <section className="landing-section landing-method" id="method" aria-labelledby="method-title">
          <div className="landing-method-intro">
            <p className="landing-eyebrow">Behind the numbers</p>
            <h2 id="method-title">The odds have<br />a method.</h2>
            <p>Results in. Possible endings out. Every model follows the competition&apos;s own format.</p>
          </div>
          <dl className="landing-method-steps">
            <div><dt><span aria-hidden="true">01</span>Start with the results</dt><dd>Public results and fixtures set the table. Sources and update times are shown on every league page.</dd></div>
            <div><dt><span aria-hidden="true">02</span>Play the season forward</dt><dd>Most sports use backtested ratings and thousands of simulated seasons. Cricket uses equal-strength result scenarios; net run rate is shown but not simulated.</dd></div>
            <div><dt><span aria-hidden="true">03</span>Count the possible endings</dt><dd>A team&apos;s chance is the share of model seasons in which it reaches that outcome. Read each league&apos;s method and limitations for the full picture.</dd></div>
          </dl>
        </section>
      </main>
      <footer className="pulse-footer"><span>Model estimates for fans, not betting advice.</span><span>Sources are credited on each league page.</span></footer>
    </>
  );
};

export default LandingPage;
