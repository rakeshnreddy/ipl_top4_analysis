import { useEffect, useMemo, useState } from 'react';
import { AlertTriangle, CalendarClock, ExternalLink, Flame, ListOrdered, ShieldCheck, Swords, Zap } from 'lucide-react';
import '../App.css';
import './SportPage.css';
import LeagueSwitcher from '../components/LeagueSwitcher';
import { leagueHref, type LeagueIndex } from '../data/leagues';
import {
  isSeasonComplete,
  loadSportData,
  type MatchThatMatters,
  type SportColumn,
  type SportFixture,
  type SportPayload,
  type SportStanding,
  type SportTier,
} from '../data/sportData';
import { formatGeneratedAt } from '../lib/standings';
import { appBaseHref, setJsonLd, setPageMeta } from '../lib/seo';
import { formatChance } from './format';

const UPCOMING_LIMIT = 10;
const RESULTS_LIMIT = 10;
// Fixtures that kicked off more than this long ago are under way or awaiting their result.
const STARTED_MS = 3 * 60 * 60 * 1000;
const OUTCOME_LABELS: Record<string, string> = { home: 'Home', draw: 'Draw', away: 'Away' };

const formatSigned = (value: number) => (value > 0 ? `+${value}` : String(value));

function formatCell(row: SportStanding, column: SportColumn) {
  const value = row[column.key];
  if (typeof value !== 'number') {
    return value === null || value === undefined ? '–' : String(value);
  }
  if (column.format === 'pct') {
    return value.toFixed(3).replace(/^0/, '');
  }
  if (column.format === 'decimal') {
    return value % 1 === 0 ? String(value) : value.toFixed(1);
  }
  return column.signed ? formatSigned(value) : String(value);
}

// Kick-offs in the reader's own time zone.
const formatKickoff = (value: string) =>
  new Intl.DateTimeFormat(undefined, {
    weekday: 'short',
    day: 'numeric',
    month: 'short',
    hour: 'numeric',
    minute: '2-digit',
    timeZoneName: 'short',
  }).format(new Date(value));

const formatDay = (value: string) =>
  new Intl.DateTimeFormat(undefined, { weekday: 'short', day: 'numeric', month: 'short' }).format(new Date(value));

function teamLookup(payload: SportPayload) {
  const teams = new Map(payload.league.teams.map((team) => [team.key, team]));
  return (key: string) =>
    teams.get(key) ?? { key, shortName: key, fullName: key, color: '#2d405f', textColor: '#ffffff' };
}

function chance(payload: SportPayload, teamKey: string, tierKey: string) {
  return payload.analysis.probabilities[teamKey]?.[tierKey] ?? 0;
}

/** Tier label list for titles: "Title, Top 4 & Relegation". */
function tierPhrase(tiers: SportTier[]) {
  const labels = tiers.map((tier) => tier.label);
  return labels.length > 1 ? `${labels.slice(0, -1).join(', ')} & ${labels[labels.length - 1]}` : labels[0] ?? 'Season';
}

function sportSeo(payload: SportPayload) {
  const { name, seasonLabel, tiers } = payload.league;
  const phrase = tierPhrase(tiers);
  if (isSeasonComplete(payload)) {
    return {
      title: `${name} ${seasonLabel} Final Table & Results | Playoff Pulse`,
      description: `The final ${name} ${seasonLabel} table with every result, plus how the season's ${phrase.toLowerCase()} races finished.`,
    };
  }
  return {
    title: `${name} ${seasonLabel} Odds: ${phrase} Chances | Playoff Pulse`,
    description: `Daily ${name} ${phrase.toLowerCase()} probabilities from ${payload.analysis.simulations.toLocaleString()} simulated seasons, with the live table, fixture predictions and the matches that matter most.`,
  };
}

/** One line per tier for the hero: the favourite, the teams most at risk, or the closest race. */
function tierHighlight(payload: SportPayload, tier: SportTier, short: (key: string) => string) {
  const ranked = payload.standings
    .map((team) => ({ key: team.teamKey, value: chance(payload, team.teamKey, tier.key) }))
    .sort((a, b) => b.value - a.value);
  if (tier.kind === 'bottom') {
    const atRisk = ranked.slice(0, Math.min(tier.size ?? 3, 3));
    return { label: `${tier.label} risk`, value: atRisk.map((item) => `${short(item.key)} ${formatChance(item.value)}`).join(' · ') };
  }
  if (tier.size === 1) {
    const favourite = ranked[0];
    return { label: `${tier.label} favourite`, value: favourite ? `${short(favourite.key)} ${formatChance(favourite.value)}` : '–' };
  }
  const bubble = [...ranked].sort((a, b) => Math.abs(a.value - 50) - Math.abs(b.value - 50)).slice(0, 2);
  return {
    label: `${tier.label} bubble`,
    value: bubble.map((item) => `${short(item.key)} ${formatChance(item.value)}`).join(' · '),
  };
}

/** Table rows inside a top tier (or the bottom one) by current position. */
function zoneFor(payload: SportPayload, rank: number) {
  const count = payload.standings.length;
  const bottom = payload.league.tiers.find((tier) => tier.kind === 'bottom' && tier.size && rank > count - tier.size);
  if (bottom) {
    return 'zone-bottom';
  }
  const tops = payload.league.tiers.filter((tier) => tier.kind === 'top' && tier.size).sort((a, b) => (a.size ?? 0) - (b.size ?? 0));
  const index = tops.findIndex((tier) => rank <= (tier.size ?? 0));
  return index === 0 ? 'zone-first' : index > 0 ? 'zone-top' : '';
}

function heatStyle(value: number, tier: SportTier) {
  const alpha = Math.min(0.75, (value / 100) * 0.75);
  const rgb = tier.kind === 'bottom' ? '244, 63, 94' : '52, 211, 153';
  return value > 0 ? { backgroundColor: `rgba(${rgb}, ${alpha.toFixed(3)})` } : undefined;
}

function teamKeyFromHash(payload: SportPayload) {
  const match = window.location.hash.match(/^#team=(.+)$/);
  if (!match) {
    return null;
  }
  const wanted = decodeURIComponent(match[1]).toLowerCase();
  return payload.standings.find((team) => team.shortName.toLowerCase() === wanted || team.teamKey.toLowerCase() === wanted)?.teamKey ?? null;
}

function scrollToSection(id: string) {
  document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

const SportPage = ({ leagueId, leagueIndex }: { leagueId: string; leagueIndex: LeagueIndex | null }) => {
  const [payload, setPayload] = useState<SportPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selectedKey, setSelectedKey] = useState('');
  const [groupKey, setGroupKey] = useState('');
  const homeLeagueId = leagueIndex?.default ?? leagueId;

  useEffect(() => {
    let active = true;
    loadSportData(fetch, leagueId)
      .then((data) => {
        if (active) {
          setPayload(data);
          setSelectedKey(teamKeyFromHash(data) ?? data.standings[0]?.teamKey ?? '');
        }
      })
      .catch((loadError: Error) => {
        if (active) {
          setError(loadError.message);
        }
      });
    return () => {
      active = false;
    };
  }, [leagueId]);

  useEffect(() => {
    if (!payload) {
      return;
    }
    const { title, description } = sportSeo(payload);
    const pageHref = new URL(leagueHref(payload.league.id, homeLeagueId), window.location.origin).href;
    setPageMeta(title, description, pageHref);
    const baseHref = appBaseHref();
    setJsonLd({
      '@context': 'https://schema.org',
      '@graph': [
        { '@type': 'WebSite', '@id': `${baseHref}#website`, name: 'Playoff Pulse', url: baseHref },
        {
          '@type': 'WebPage',
          '@id': `${pageHref}#webpage`,
          name: title,
          description,
          url: pageHref,
          dateModified: payload.metadata.generated_at,
          isPartOf: { '@id': `${baseHref}#website` },
        },
        {
          '@type': 'Dataset',
          '@id': `${pageHref}#dataset`,
          name: title.split(' | ')[0],
          description,
          url: new URL(`${import.meta.env.BASE_URL}data/${payload.league.id}.json`, window.location.origin).href,
          dateModified: payload.metadata.generated_at,
          creator: { '@type': 'Organization', name: payload.metadata.source },
        },
      ],
    });
  }, [payload, homeLeagueId]);

  useEffect(() => {
    if (!payload) {
      return undefined;
    }
    const syncFromHash = () => {
      const key = teamKeyFromHash(payload);
      if (key) {
        setSelectedKey(key);
        scrollToSection('team');
      }
    };
    window.addEventListener('hashchange', syncFromHash);
    return () => window.removeEventListener('hashchange', syncFromHash);
  }, [payload]);

  const team = useMemo(() => (payload ? teamLookup(payload) : null), [payload]);

  if (error) {
    return (
      <main className="pulse-app pulse-center">
        <section className="error-panel" role="alert">
          <AlertTriangle aria-hidden="true" />
          <h1>This league could not load</h1>
          <p>{error}</p>
          <a href={import.meta.env.BASE_URL}>Go to the home page</a>
        </section>
      </main>
    );
  }

  if (!payload || !team) {
    return (
      <main className="pulse-app pulse-center">
        <div className="loading-panel" role="status" aria-live="polite">
          <Flame aria-hidden="true" />
          <span>Loading Playoff Pulse...</span>
        </div>
      </main>
    );
  }

  const short = (key: string) => team(key).shortName;
  const complete = isSeasonComplete(payload);
  const started = payload.standings.some((row) => row.played > 0);
  const selected = payload.standings.find((row) => row.teamKey === selectedKey) ?? payload.standings[0];
  const groups = payload.league.groups ?? [];
  const group = groups.find((item) => item.key === groupKey);
  const rows = group ? payload.standings.filter((row) => group.teams.includes(row.teamKey)) : payload.standings;

  const selectTeam = (key: string) => {
    setSelectedKey(key);
    window.history.replaceState(null, '', `#team=${encodeURIComponent(short(key))}`);
    scrollToSection('team');
  };

  return (
    <main className="pulse-app sport-page" data-testid="sport-page">
      <LeagueSwitcher currentId={payload.league.id} index={leagueIndex} />

      <section className="hero-band compact-hero" aria-labelledby="page-title">
        <div className="hero-copy">
          <div className="hero-main">
            <span className="eyebrow">
              <Zap size={14} aria-hidden="true" />
              {payload.league.shortName} · {payload.league.seasonLabel}
            </span>
            <h1 id="page-title">
              {complete
                ? `${payload.league.name} ${payload.league.seasonLabel} Final Table`
                : `${payload.league.name} ${tierPhrase(payload.league.tiers)} Odds`}
            </h1>
            <p>
              {complete
                ? 'The season is over: final table, last results and how each race finished.'
                : `Updated daily from ${payload.analysis.simulations.toLocaleString()} simulated seasons`}
            </p>
            <nav className="quick-links" aria-label="Page sections">
              <a href="#table">Table</a>
              {!complete && <a href="#fixtures">Fixtures</a>}
              {payload.matchesThatMatter.length > 0 && <a href="#matters">Matches that matter</a>}
              <a href="#team">Team view</a>
              <a href="#method">How it works</a>
            </nav>
          </div>

          <div className="hero-facts" aria-label="Season snapshot">
            {payload.league.tiers.slice(0, 3).map((tier) => {
              const highlight = complete
                ? { label: tier.label, value: payload.standings.filter((row) => chance(payload, row.teamKey, tier.key) >= 50).map((row) => row.shortName).join(', ') || '–' }
                : tierHighlight(payload, tier, short);
              return (
                <div key={tier.key}>
                  <span>{highlight.label}</span>
                  <strong>{started || complete ? highlight.value : 'Season not started'}</strong>
                </div>
              );
            })}
            <div>
              <span>Latest update</span>
              <strong data-testid="latest-update">{formatGeneratedAt(payload.metadata.generated_at)}</strong>
            </div>
          </div>

          <div className="hero-meta">
            <span>Source: {payload.metadata.source}</span>
            <span>{payload.analysis.model}</span>
            {!complete && <span>{payload.analysis.method}</span>}
          </div>
        </div>
      </section>

      {!complete && payload.movement && <MovementPanel payload={payload} short={short} />}

      <section className="sport-grid">
        <div className="ladder-panel sport-table-panel" id="table">
          <div className="section-heading">
            <div>
              <span className="panel-kicker">{complete ? 'Final' : 'Live'} table</span>
              <h2>{complete ? 'Final Table' : 'Table & Season Odds'}</h2>
            </div>
            <ListOrdered aria-hidden="true" />
          </div>

          {groups.length > 0 && (
            <div className="goal-tabs sport-group-tabs" role="group" aria-label="Table view">
              <button className={!group ? 'active' : ''} onClick={() => setGroupKey('')} type="button">
                {payload.league.rankLabel ?? 'All'}
              </button>
              {groups.map((item) => (
                <button className={group?.key === item.key ? 'active' : ''} key={item.key} onClick={() => setGroupKey(item.key)} type="button">
                  {item.label}
                </button>
              ))}
            </div>
          )}

          <div className="table-scroll">
            <table className="sport-table">
              <thead>
                <tr>
                  <th scope="col" className="col-rank">#</th>
                  <th scope="col" className="col-team">Team</th>
                  {payload.league.columns.map((column) => (
                    <th
                      scope="col"
                      key={column.key}
                      title={column.title}
                      className={['wins', 'draws', 'losses', 'goalsFor', 'goalsAgainst'].includes(column.key) ? 'col-optional' : undefined}
                    >
                      {column.label}
                    </th>
                  ))}
                  <th scope="col" className="col-form" title="Last five results, latest on the right">
                    Form
                  </th>
                  {payload.league.tiers.map((tier) => (
                    <th scope="col" className="col-tier" key={tier.key} title={tier.label}>
                      {tier.shortLabel ? (
                        <>
                          <span className="label-full">{tier.label}</span>
                          <span className="label-short" aria-hidden="true">
                            {tier.shortLabel}
                          </span>
                        </>
                      ) : (
                        tier.label
                      )}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((row, position) => (
                  <tr
                    className={`${group ? '' : zoneFor(payload, row.rank)} ${row.teamKey === selected.teamKey ? 'is-selected' : ''}`}
                    key={row.teamKey}
                    onClick={() => selectTeam(row.teamKey)}
                  >
                    <td className="col-rank">{group ? position + 1 : row.rank}</td>
                    <th scope="row" className="col-team">
                      <button type="button" onClick={(event) => { event.stopPropagation(); selectTeam(row.teamKey); }}>
                        <span className="team-chip" style={{ backgroundColor: team(row.teamKey).color }} aria-hidden="true" />
                        <strong>{row.shortName}</strong>
                        <small>{row.fullName}</small>
                      </button>
                    </th>
                    {payload.league.columns.map((column) => (
                      <td
                        key={column.key}
                        className={`${column.strong ? 'is-strong' : ''} ${['wins', 'draws', 'losses', 'goalsFor', 'goalsAgainst'].includes(column.key) ? 'col-optional' : ''}`}
                      >
                        {formatCell(row, column)}
                      </td>
                    ))}
                    <td className="col-form">
                      <FormStrip form={row.form} />
                    </td>
                    {payload.league.tiers.map((tier) => {
                      const value = chance(payload, row.teamKey, tier.key);
                      return complete ? (
                        <td className={`col-tier ${value >= 50 ? 'is-achieved' : 'is-missed'}`} key={tier.key}>
                          {value >= 50 ? '✓' : '–'}
                        </td>
                      ) : (
                        <td className="col-tier" key={tier.key} style={heatStyle(value, tier)}>
                          {formatChance(value)}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="probability-note">
            {complete
              ? 'Final positions; ties are broken by the league rules shown in How it works.'
              : 'Season odds count every remaining fixture. Tap a team for its finishing-position chances and next games.'}
          </p>
        </div>

        <TeamPanel payload={payload} row={selected} short={short} team={team} />
      </section>

      {!complete && <FixturesPanel payload={payload} short={short} team={team} />}
      {payload.matchesThatMatter.length > 0 && <MattersPanel payload={payload} short={short} />}
      <ResultsPanel payload={payload} short={short} />

      <section className="race-summary-panel sport-method" id="method" aria-labelledby="method-title">
        <div className="section-heading">
          <div>
            <span className="panel-kicker">Method</span>
            <h2 id="method-title">How These Odds Work</h2>
          </div>
          <ShieldCheck aria-hidden="true" />
        </div>
        <ul>
          {payload.analysis.modelNotes.map((note) => (
            <li key={note}>{note}</li>
          ))}
          <li>These are model estimates for fans, not betting advice.</li>
        </ul>
      </section>

      <footer className="pulse-footer">
        <span>
          Updated {formatGeneratedAt(payload.metadata.generated_at)} · {payload.analysis.model}
          {!complete && <> · {payload.analysis.simulations.toLocaleString()} simulations</>}
        </span>
        <a href={payload.metadata.source_url} target="_blank" rel="noreferrer">
          Fixtures and results: {payload.metadata.source}
          <ExternalLink size={12} aria-hidden="true" />
        </a>
        {(payload.metadata.credits ?? []).map((credit) => (
          <a href={credit.url} key={credit.name} target="_blank" rel="noreferrer">
            {credit.note ?? credit.name}
            <ExternalLink size={12} aria-hidden="true" />
          </a>
        ))}
        {payload.metadata.warnings.length > 0 && (
          <span className="footer-warning" data-testid="freshness-warning">
            Data note: {payload.metadata.warnings.join(' ')}
          </span>
        )}
      </footer>
    </main>
  );
};

type ShortName = (key: string) => string;
type TeamLookup = ReturnType<typeof teamLookup>;

/** Payload form is latest first; it reads left to right here, ending with the latest game. */
const FormStrip = ({ form }: { form: string[] }) => {
  const oldestFirst = [...form].reverse();
  return (
    <span
      className="form-strip"
      aria-label={form.length ? `Last ${form.length}, oldest first: ${oldestFirst.join(' ')}` : 'No games yet'}
      title="Last five results, latest on the right"
    >
      {oldestFirst.map((result, index) => (
        <span className={`form-${result.toLowerCase()}`} key={index}>
          {result}
        </span>
      ))}
    </span>
  );
};

const MovementPanel = ({ payload, short }: { payload: SportPayload; short: ShortName }) => {
  const movement = payload.movement;
  if (!movement) {
    return null;
  }
  const moves = payload.league.tiers.map((tier) => {
    const deltas = Object.entries(movement.changes)
      .map(([key, values]) => [key, values[tier.key] ?? 0] as const)
      .filter(([, delta]) => Math.abs(delta) >= 0.5);
    const up = [...deltas].sort((a, b) => b[1] - a[1])[0];
    const down = [...deltas].sort((a, b) => a[1] - b[1])[0];
    return { tier, up: up && up[1] > 0 ? up : null, down: down && down[1] < 0 ? down : null };
  });
  if (moves.every((move) => !move.up && !move.down)) {
    return null;
  }
  const describe = (entry: readonly [string, number] | null) =>
    entry ? `${short(entry[0])} ${entry[1] > 0 ? '+' : ''}${entry[1].toFixed(1)}` : 'No big change';

  return (
    <section className="race-summary-panel" aria-labelledby="movement-title">
      <div className="section-heading">
        <div>
          <span className="panel-kicker">Since {formatGeneratedAt(movement.since)}</span>
          <h2 id="movement-title">Biggest Moves</h2>
        </div>
        <Zap aria-hidden="true" />
      </div>
      <div className="race-summary-grid sport-movement-grid">
        {moves.map(({ tier, up, down }) => (
          <article key={tier.key}>
            <span>{tier.label}</span>
            <strong>
              {tier.kind === 'bottom' ? describe(down) : describe(up)}
            </strong>
            <small>
              {tier.kind === 'bottom' ? 'Biggest escape' : 'Biggest rise'} · then {tier.kind === 'bottom' ? describe(up) : describe(down)}{' '}
              {tier.kind === 'bottom' ? 'closer to the drop' : 'biggest fall'}
            </small>
          </article>
        ))}
      </div>
    </section>
  );
};

const OutcomeBar = ({ fixture, team }: { fixture: SportFixture; team: TeamLookup }) => {
  const home = team(fixture.home);
  const away = team(fixture.away);
  const segments = Object.entries(fixture.probabilities);
  return (
    <span className="outcome-bar" role="img" aria-label={segments.map(([key, value]) => `${OUTCOME_LABELS[key] ?? key} ${Math.round(value * 100)}%`).join(', ')}>
      {segments.map(([key, value]) => (
        <span
          className={`outcome-${key}`}
          key={key}
          style={{
            width: `${Math.max(value * 100, 6)}%`,
            backgroundColor: key === 'home' ? home.color : key === 'away' ? away.color : undefined,
            color: key === 'home' ? home.textColor : key === 'away' ? away.textColor : undefined,
          }}
        >
          {Math.round(value * 100)}%
        </span>
      ))}
    </span>
  );
};

const FixturesPanel = ({ payload, short, team }: { payload: SportPayload; short: ShortName; team: TeamLookup }) => {
  const now = Date.now();
  const upcoming = payload.fixtures.filter((fixture) => Date.parse(fixture.date) > now - STARTED_MS).slice(0, UPCOMING_LIMIT);
  if (upcoming.length === 0) {
    return null;
  }
  const hasDraw = payload.league.outcomes.includes('draw');
  return (
    <section className="race-summary-panel" id="fixtures" aria-labelledby="fixtures-title">
      <div className="section-heading">
        <div>
          <span className="panel-kicker">Next up</span>
          <h2 id="fixtures-title">Fixture Predictions</h2>
        </div>
        <CalendarClock aria-hidden="true" />
      </div>
      <ol className="sport-fixtures">
        {upcoming.map((fixture) => (
          <li key={fixture.id}>
            <span className="fixture-when">{formatKickoff(fixture.date)}</span>
            <span className="fixture-teams">
              <strong>{short(fixture.home)}</strong> vs <strong>{short(fixture.away)}</strong>
            </span>
            <OutcomeBar fixture={fixture} team={team} />
          </li>
        ))}
      </ol>
      <p className="probability-note">
        {hasDraw ? 'Home win, draw and away win chances from the goals model.' : 'Home and away win chances from the ratings model.'}
      </p>
    </section>
  );
};

const MattersPanel = ({ payload, short }: { payload: SportPayload; short: ShortName }) => (
  <section className="race-summary-panel" id="matters" aria-labelledby="matters-title">
    <div className="section-heading">
      <div>
        <span className="panel-kicker">Swing games</span>
        <h2 id="matters-title">Matches That Matter</h2>
      </div>
      <Swords aria-hidden="true" />
    </div>
    <div className="matters-grid">
      {payload.matchesThatMatter.map((match: MatchThatMatters) => (
        <article key={match.fixtureId}>
          <span>
            {formatDay(match.date)} · {match.tierLabel}
          </span>
          <strong>
            {short(match.home)} vs {short(match.away)}
          </strong>
          <small>
            {short(match.team)}&apos;s {match.tierLabel.toLowerCase()} chance after each result
          </small>
          <dl>
            <div>
              <dt>{short(match.home)} win</dt>
              <dd>{match.ifHome === null ? '–' : formatChance(match.ifHome)}</dd>
            </div>
            {match.ifDraw !== undefined && (
              <div>
                <dt>Draw</dt>
                <dd>{match.ifDraw === null ? '–' : formatChance(match.ifDraw)}</dd>
              </div>
            )}
            <div>
              <dt>{short(match.away)} win</dt>
              <dd>{match.ifAway === null ? '–' : formatChance(match.ifAway)}</dd>
            </div>
          </dl>
        </article>
      ))}
    </div>
  </section>
);

const ResultsPanel = ({ payload, short }: { payload: SportPayload; short: ShortName }) => {
  if (payload.results.length === 0) {
    return null;
  }
  return (
    <section className="race-summary-panel" aria-labelledby="results-title">
      <div className="section-heading">
        <div>
          <span className="panel-kicker">Latest</span>
          <h2 id="results-title">Recent Results</h2>
        </div>
      </div>
      <ol className="sport-results">
        {payload.results.slice(0, RESULTS_LIMIT).map((result) => (
          <li key={result.id}>
            <span className="fixture-when">{formatDay(result.date)}</span>
            <span className={result.homeScore > result.awayScore ? 'is-winner' : ''}>{short(result.home)}</span>
            <strong>
              {result.homeScore}–{result.awayScore}
              {result.note ? <small> {result.note}</small> : null}
            </strong>
            <span className={result.awayScore > result.homeScore ? 'is-winner' : ''}>{short(result.away)}</span>
          </li>
        ))}
      </ol>
    </section>
  );
};

const TeamPanel = ({ payload, row, short, team }: { payload: SportPayload; row: SportStanding; short: ShortName; team: TeamLookup }) => {
  const meta = team(row.teamKey);
  const complete = isSeasonComplete(payload);
  const positions = payload.analysis.positions?.[row.teamKey] ?? [];
  const expected = payload.analysis.expected?.[row.teamKey];
  const peak = Math.max(...positions, 1);
  const count = payload.standings.length;
  const next = payload.fixtures.filter((fixture) => fixture.home === row.teamKey || fixture.away === row.teamKey).slice(0, 5);
  const recent = payload.results.filter((result) => result.home === row.teamKey || result.away === row.teamKey).slice(0, 5);
  const bottomSize = payload.league.tiers.find((tier) => tier.kind === 'bottom')?.size ?? 0;
  const topSize = Math.max(0, ...payload.league.tiers.filter((tier) => tier.kind === 'top').map((tier) => tier.size ?? 0));
  const positionLabel = payload.league.positionLabel ?? 'Finishing position';

  return (
    <aside className="probability-panel sport-team-panel" id="team" aria-labelledby="team-title">
      <div className="spotlight-title">
        <span style={{ backgroundColor: meta.color, color: meta.textColor }}>{row.shortName}</span>
        <div>
          <span className="panel-kicker">Team view</span>
          <h2 id="team-title">{row.fullName}</h2>
        </div>
      </div>

      <dl className="team-facts">
        <div>
          <dt>Now</dt>
          <dd>
            {row.rank}
            <small>{ordinalSuffix(row.rank)}</small>
            {row.points !== undefined ? ` · ${row.points} pts` : ` · ${row.wins}-${row.losses}`}
          </dd>
        </div>
        {!complete && expected && (
          <div>
            <dt>Projected</dt>
            <dd>
              {expected.points !== undefined ? `${expected.points.toFixed(0)} pts` : `${expected.wins?.toFixed(0)} wins`}
              {expected.position !== undefined ? ` · avg ${expected.position.toFixed(1)}` : ''}
            </dd>
          </div>
        )}
        {payload.league.tiers.map((tier) => (
          <div key={tier.key}>
            <dt>{tier.label}</dt>
            <dd>{complete ? (chance(payload, row.teamKey, tier.key) >= 50 ? 'Yes' : 'No') : formatChance(chance(payload, row.teamKey, tier.key))}</dd>
          </div>
        ))}
      </dl>

      {!complete && positions.length > 0 && (
        <div className="position-chart" role="img" aria-label={`${positionLabel} chances for ${row.shortName}`}>
          <h3>{positionLabel}</h3>
          <div className="position-bars">
            {positions.map((value, index) => {
              const place = index + 1;
              const zone = place > count - bottomSize ? 'zone-bottom' : place <= topSize ? 'zone-top' : '';
              return (
                <span className={`position-bar ${zone}`} key={place} title={`${place}${ordinalSuffix(place)}: ${formatChance(value)}`}>
                  <span style={{ height: `${Math.max((value / peak) * 100, value > 0 ? 3 : 0)}%` }} />
                  <small>{place}</small>
                </span>
              );
            })}
          </div>
        </div>
      )}

      {next.length > 0 && (
        <div className="team-next">
          <h3>Next games</h3>
          <ul className="fixture-list">
            {next.map((fixture) => {
              const home = fixture.home === row.teamKey;
              const win = home ? fixture.probabilities.home : fixture.probabilities.away;
              const loss = home ? fixture.probabilities.away : fixture.probabilities.home;
              return (
                <li key={fixture.id}>
                  <span>
                    {home ? 'vs' : '@'} <strong>{short(home ? fixture.away : fixture.home)}</strong> · {formatDay(fixture.date)}
                  </span>
                  <small>
                    Win {Math.round(win * 100)}%
                    {fixture.probabilities.draw !== undefined && ` · Draw ${Math.round(fixture.probabilities.draw * 100)}%`} · Loss{' '}
                    {Math.round(loss * 100)}%
                  </small>
                </li>
              );
            })}
          </ul>
        </div>
      )}

      {recent.length > 0 && (
        <div className="team-next">
          <h3>Latest results</h3>
          <ul className="fixture-list">
            {recent.map((result) => {
              const home = result.home === row.teamKey;
              const own = home ? result.homeScore : result.awayScore;
              const other = home ? result.awayScore : result.homeScore;
              const outcome = own > other ? 'W' : own === other ? 'D' : 'L';
              return (
                <li key={result.id}>
                  <span>
                    <b className={`form-${outcome.toLowerCase()}`}>{outcome}</b> {own}–{other} {home ? 'vs' : '@'}{' '}
                    <strong>{short(home ? result.away : result.home)}</strong>
                  </span>
                  <small>{formatDay(result.date)}</small>
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </aside>
  );
};

function ordinalSuffix(value: number) {
  const suffixes = ['th', 'st', 'nd', 'rd'];
  const lastTwo = value % 100;
  return suffixes[(lastTwo - 20) % 10] || suffixes[lastTwo] || suffixes[0];
}

export default SportPage;
