import { useEffect, useMemo, useState } from 'react';
import { ExternalLink } from 'lucide-react';
import '../App.css';
import './F1Page.css';
import PageHeader, { type StatusTone } from '../components/PageHeader';
import { ErrorState, LoadingState } from '../components/PageState';
import SiteHeader from '../components/SiteHeader';
import { leagueHref, sportName, type LeagueIndex } from '../data/leagues';
import { formatGeneratedAt } from '../lib/standings';
import { appBaseHref, setJsonLd, setPageMeta } from '../lib/seo';
import { heatStyle, samePageHref } from '../lib/ui';
import { formatChance } from '../sport/format';
import { loadF1Data, type F1Event, type F1Payload, type F1Team, type F1Tier } from './f1Data';

const NEXT_EVENTS = 4;
const RESULTS_LIMIT = 8;

// Start times in the reader's own time zone.
const formatStart = (value: string) =>
  new Intl.DateTimeFormat(undefined, {
    weekday: 'short',
    day: 'numeric',
    month: 'short',
    hour: 'numeric',
    minute: '2-digit',
    timeZoneName: 'short',
  }).format(new Date(value));

const formatDay = (value: string) => new Intl.DateTimeFormat(undefined, { day: 'numeric', month: 'short' }).format(new Date(value));

const eventLabel = (event: F1Event) => (event.kind === 'sprint' ? `${event.name} · Sprint` : event.name);

const isComplete = (payload: F1Payload) => payload.metadata.season_status === 'complete';

function seo(payload: F1Payload) {
  const { name, shortName, seasonLabel } = payload.league;
  if (isComplete(payload)) {
    return {
      title: `${shortName} ${seasonLabel} Final Standings: Drivers' & Constructors' Championships | Playoff Pulse`,
      description: `The final ${name} ${seasonLabel} drivers' and constructors' standings, with the last race results.`,
    };
  }
  return {
    title: `${shortName} ${seasonLabel} Title Odds: Drivers' & Constructors' Championship Chances | Playoff Pulse`,
    description: `Daily ${name} ${seasonLabel} drivers' and constructors' title odds from ${payload.analysis.simulations.toLocaleString()} simulated seasons, with the standings, win and podium favourites for every remaining race and the latest results.`,
  };
}

function status(payload: F1Payload, started: boolean): { label: string; tone: StatusTone } {
  if (isComplete(payload)) {
    return { label: 'Final', tone: 'final' };
  }
  return started ? { label: 'Live', tone: 'live' } : { label: 'Pre-season', tone: 'pre-season' };
}

/** The key of a tier by kind: the title ("champion") or the top-N place. */
const tierOf = (tiers: F1Tier[], kind: string) => tiers.find((tier) => tier.kind === kind);

const ChampionMark = ({ achieved, label }: { achieved: boolean; label: string }) => (
  <>
    <span aria-hidden="true" className={achieved ? 'mark-yes' : 'mark-no'}>
      {achieved ? '✓' : '–'}
    </span>
    <span className="visually-hidden">{achieved ? `${label}: yes` : `${label}: no`}</span>
  </>
);

/** A driver's or team's name with its team colour (from the data) as a chip. */
const Named = ({ team, code, name }: { team: F1Team | undefined; code: string; name?: string }) => (
  <span className="f1-name">
    <span className="team-chip" style={team ? { backgroundColor: team.color } : undefined} aria-hidden="true" />
    <strong>{code}</strong>
    {name && <small>{name}</small>}
  </span>
);

const F1Page = ({ leagueId, leagueIndex }: { leagueId: string; leagueIndex: LeagueIndex | null }) => {
  const [payload, setPayload] = useState<F1Payload | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    loadF1Data(fetch, leagueId)
      .then((data) => {
        if (active) {
          setPayload(data);
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
    const { title, description } = seo(payload);
    const pageHref = new URL(leagueHref(payload.league.id), window.location.origin).href;
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
  }, [payload]);

  const teams = useMemo(() => new Map((payload?.league.teams ?? []).map((team) => [team.key, team])), [payload]);

  if (error) {
    return (
      <>
        <SiteHeader currentId={leagueId} index={leagueIndex} />
        <ErrorState homeHref={import.meta.env.BASE_URL} message={error} title="This league could not load" />
      </>
    );
  }

  if (!payload) {
    return (
      <>
        <SiteHeader currentId={leagueId} index={leagueIndex} />
        <LoadingState />
      </>
    );
  }

  const complete = isComplete(payload);
  const started = payload.standings.some((row) => row.played > 0);
  const drivers = new Map(payload.standings.map((row) => [row.teamKey, row]));
  const code = (driver: string) => drivers.get(driver)?.shortName ?? driver;
  const teamOf = (driver: string) => teams.get(drivers.get(driver)?.team ?? '');
  const driverTitle = tierOf(payload.league.tiers, 'champion');
  const driverTop = tierOf(payload.league.tiers, 'top');
  const teamTitle = tierOf(payload.league.constructorTiers, 'champion');
  const chance = (key: string, tier: F1Tier | undefined) => (tier ? payload.analysis.probabilities[key]?.[tier.key] ?? 0 : 0);
  const teamChance = (key: string) => (teamTitle ? payload.analysis.constructorProbabilities[key]?.[teamTitle.key] ?? 0 : 0);

  const favourite = [...payload.standings].sort((a, b) => chance(b.teamKey, driverTitle) - chance(a.teamKey, driverTitle))[0];
  const teamFavourite = [...payload.constructorStandings].sort((a, b) => teamChance(b.teamKey) - teamChance(a.teamKey))[0];
  const nextEvent = payload.events[0];
  const facts = [
    complete
      ? { label: "Drivers' champion", value: favourite ? `${favourite.fullName} (${favourite.shortName})` : '–' }
      : {
          label: `${driverTitle?.label ?? 'Title'} favourite`,
          value: favourite ? `${favourite.shortName} ${formatChance(chance(favourite.teamKey, driverTitle))}` : '–',
        },
    complete
      ? { label: "Constructors' champion", value: teamFavourite?.fullName ?? '–' }
      : {
          label: `${teamTitle?.label ?? 'Constructors'} favourite`,
          value: teamFavourite ? `${teamFavourite.shortName} ${formatChance(teamChance(teamFavourite.teamKey))}` : '–',
        },
    ...(nextEvent ? [{ label: nextEvent.kind === 'sprint' ? 'Next: sprint' : 'Next race', value: `${nextEvent.name}, ${formatDay(nextEvent.date)}` }] : []),
    { label: 'Latest update', value: formatGeneratedAt(payload.metadata.generated_at), testId: 'latest-update' },
  ];
  const sections = [
    { href: '#drivers', label: 'Drivers' },
    { href: '#constructors', label: 'Constructors' },
    ...(!complete && payload.events.length > 0 ? [{ href: '#races', label: 'Next races' }] : []),
    ...(payload.results.length > 0 ? [{ href: '#results', label: 'Results' }] : []),
    { href: '#method', label: 'How it works' },
  ];
  const races = payload.events.filter((event) => event.kind === 'race').length;

  return (
    <>
      <a className="skip-link" href={samePageHref('#main')}>
        Skip to content
      </a>
      <SiteHeader currentId={payload.league.id} currentLabel={`${payload.league.shortName} ${payload.league.seasonLabel}`} index={leagueIndex} />
      <main className="pulse-app f1-page" data-testid="f1-page" id="main">
        <PageHeader
          crumb={`${sportName(payload.league.sport)} · ${payload.league.shortName} ${payload.league.seasonLabel}`}
          facts={facts}
          factsLabel="Season snapshot"
          sections={sections}
          status={status(payload, started)}
          strap={
            complete
              ? 'The season is over: the final standings and the last results.'
              : started
                ? `Updated daily from ${payload.analysis.simulations.toLocaleString()} simulated seasons: ${races} race${races === 1 ? '' : 's'} and ${payload.events.length - races} sprint${payload.events.length - races === 1 ? '' : 's'} to go.`
                : `Pre-season projections from ${payload.analysis.simulations.toLocaleString()} simulated seasons.`
          }
          title={complete ? `${payload.league.name} ${payload.league.seasonLabel} Final Standings` : (payload.league.headline ?? `${payload.league.name} Title Odds`)}
        />

        <section className="panel" id="drivers" aria-labelledby="drivers-title">
          <div className="section-heading">
            <h2 id="drivers-title">Drivers' Championship</h2>
            <p>{complete ? 'Final standings' : 'Points so far, and the chance of each finish'}</p>
          </div>
          <div className="table-scroll">
            <table className="data-table f1-table">
              <caption className="visually-hidden">Drivers' standings{complete ? '' : ' with title and top-three odds'}</caption>
              <thead>
                <tr>
                  <th scope="col" className="col-rank">
                    <abbr title="Position">#</abbr>
                  </th>
                  <th scope="col" className="col-team">
                    Driver
                  </th>
                  <th scope="col" className="col-optional">
                    Team
                  </th>
                  <th scope="col">
                    <abbr title="Points">Pts</abbr>
                  </th>
                  <th scope="col">Wins</th>
                  <th scope="col" className="col-optional">
                    Podiums
                  </th>
                  {[driverTitle, driverTop].map((tier) =>
                    tier ? (
                      <th scope="col" className="col-tier" key={tier.key} title={tier.label}>
                        {tier.shortLabel && tier.shortLabel !== tier.label ? <abbr title={tier.label}>{tier.shortLabel}</abbr> : tier.label}
                      </th>
                    ) : null,
                  )}
                </tr>
              </thead>
              <tbody>
                {payload.standings.map((row) => {
                  const team = teams.get(row.team ?? '');
                  return (
                    <tr className={row.rank === 1 ? 'zone-first' : row.rank <= (driverTop?.size ?? 3) ? 'zone-top' : ''} key={row.teamKey}>
                      <td className="col-rank">{row.rank}</td>
                      <th scope="row" className="col-team">
                        <Named code={row.shortName} name={row.fullName} team={team} />
                      </th>
                      <td className="col-optional f1-team-cell">{team?.fullName ?? '–'}</td>
                      <td className="is-strong">{row.points}</td>
                      <td>{row.wins}</td>
                      <td className="col-optional">{row.podiums}</td>
                      {[driverTitle, driverTop].map((tier) => {
                        if (!tier) {
                          return null;
                        }
                        const value = chance(row.teamKey, tier);
                        return complete ? (
                          <td className="col-tier" key={tier.key}>
                            <ChampionMark achieved={value >= 50} label={tier.label} />
                          </td>
                        ) : (
                          <td className="col-tier" key={tier.key} style={heatStyle(value, 'good')}>
                            {formatChance(value)}
                          </td>
                        );
                      })}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <p className="probability-note">
            Drivers level on points are ranked by race wins, then second places, and so on; sprints do not count.
            {payload.standings.some((row) => !row.racing) && ' Drivers no longer in a race seat keep their points.'}
          </p>
        </section>

        <section className="panel" id="constructors" aria-labelledby="constructors-title">
          <div className="section-heading">
            <h2 id="constructors-title">Constructors' Championship</h2>
            <p>Both cars score for their team</p>
          </div>
          <div className="table-scroll">
            <table className="data-table f1-table">
              <caption className="visually-hidden">Constructors' standings{complete ? '' : ' with title odds'}</caption>
              <thead>
                <tr>
                  <th scope="col" className="col-rank">
                    <abbr title="Position">#</abbr>
                  </th>
                  <th scope="col" className="col-team">
                    Team
                  </th>
                  <th scope="col">
                    <abbr title="Points">Pts</abbr>
                  </th>
                  <th scope="col">Wins</th>
                  <th scope="col" className="col-optional">
                    Podiums
                  </th>
                  {teamTitle && (
                    <th scope="col" className="col-tier" title={teamTitle.label}>
                      {teamTitle.shortLabel && teamTitle.shortLabel !== teamTitle.label ? <abbr title={teamTitle.label}>{teamTitle.shortLabel}</abbr> : teamTitle.label}
                    </th>
                  )}
                </tr>
              </thead>
              <tbody>
                {payload.constructorStandings.map((row) => {
                  const value = teamChance(row.teamKey);
                  return (
                    <tr className={row.rank === 1 ? 'zone-first' : ''} key={row.teamKey}>
                      <td className="col-rank">{row.rank}</td>
                      <th scope="row" className="col-team">
                        <Named code={row.fullName} name={row.drivers.map(code).join(' · ')} team={teams.get(row.teamKey)} />
                      </th>
                      <td className="is-strong">{row.points}</td>
                      <td>{row.wins}</td>
                      <td className="col-optional">{row.podiums}</td>
                      {teamTitle &&
                        (complete ? (
                          <td className="col-tier">
                            <ChampionMark achieved={value >= 50} label={teamTitle.label} />
                          </td>
                        ) : (
                          <td className="col-tier" style={heatStyle(value, 'good')}>
                            {formatChance(value)}
                          </td>
                        ))}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>

        {!complete && payload.events.length > 0 && (
          <section className="panel" id="races" aria-labelledby="races-title">
            <div className="section-heading">
              <h2 id="races-title">Next Races</h2>
              <p>Win and podium chances of the favourites, retirements included</p>
            </div>
            <div className="f1-events">
              {payload.events.slice(0, NEXT_EVENTS).map((event) => (
                <article key={event.key} aria-labelledby={`event-${event.key}`}>
                  <span className="mini-label">
                    Round {event.round} · {event.kind === 'sprint' ? 'Sprint' : 'Grand Prix'}
                  </span>
                  <h3 id={`event-${event.key}`}>{eventLabel(event)}</h3>
                  <p className="f1-when">
                    {formatStart(event.date)}
                    {event.locality ? ` · ${event.locality}, ${event.country}` : ''}
                  </p>
                  <table className="data-table f1-table f1-favourites">
                    <caption className="visually-hidden">Favourites for the {eventLabel(event)}</caption>
                    <thead>
                      <tr>
                        <th scope="col" className="col-team">
                          Driver
                        </th>
                        <th scope="col">Win</th>
                        <th scope="col">Podium</th>
                      </tr>
                    </thead>
                    <tbody>
                      {event.favourites.map((item) => (
                        <tr key={item.driver}>
                          <th scope="row" className="col-team">
                            <Named code={code(item.driver)} team={teamOf(item.driver)} />
                          </th>
                          <td style={heatStyle(item.win, 'good')}>{formatChance(item.win)}</td>
                          <td style={heatStyle(item.podium, 'good')}>{formatChance(item.podium)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </article>
              ))}
            </div>
          </section>
        )}

        {payload.results.length > 0 && (
          <section className="panel" id="results" aria-labelledby="results-title">
            <div className="section-heading">
              <h2 id="results-title">Recent Results</h2>
              <p>Winner and podium</p>
            </div>
            <ol className="f1-results">
              {payload.results.slice(0, RESULTS_LIMIT).map((result) => (
                <li key={result.key}>
                  <span className="f1-when">
                    {formatDay(result.date)} · Round {result.round}
                  </span>
                  <strong>{eventLabel(result)}</strong>
                  <ol className="f1-podium" aria-label={`Podium: ${result.podium.map(code).join(', ')}`}>
                    {result.podium.map((driver, index) => (
                      <li key={driver}>
                        <span className="f1-place">{index + 1}</span>
                        <Named code={code(driver)} team={teamOf(driver)} />
                      </li>
                    ))}
                  </ol>
                </li>
              ))}
            </ol>
          </section>
        )}

        <section className="panel f1-method" id="method" aria-labelledby="method-title">
          <div className="section-heading">
            <h2 id="method-title">How These Odds Work</h2>
          </div>
          <ul>
            {payload.analysis.modelNotes.map((note) => (
              <li key={note}>{note}</li>
            ))}
            {(payload.metadata.notes ?? []).map((note) => (
              <li key={note}>{note}</li>
            ))}
            {payload.league.rules && (
              <li>
                Rules: {payload.league.rules.summary}{' '}
                {payload.league.rules.sources.map((source, index) => (
                  <span key={source.url}>
                    {index > 0 && ' · '}
                    <a href={source.url} target="_blank" rel="noreferrer">
                      {source.label}
                    </a>
                  </span>
                ))}
              </li>
            )}
          </ul>
        </section>
      </main>

      <footer className="pulse-footer">
        <span>Model estimates for fans, not betting advice.</span>
        <span>
          Updated {formatGeneratedAt(payload.metadata.generated_at)} · {payload.analysis.model}
          {!complete && <> · {payload.analysis.simulations.toLocaleString()} simulations</>}
        </span>
        <a href={payload.metadata.source_url} target="_blank" rel="noreferrer">
          Results and standings: {payload.metadata.source}
          <ExternalLink size={12} aria-hidden="true" />
        </a>
        {payload.metadata.warnings.length > 0 && (
          <span className="footer-warning" data-testid="freshness-warning">
            Data note: {payload.metadata.warnings.join(' ')}
          </span>
        )}
      </footer>
    </>
  );
};

export default F1Page;
