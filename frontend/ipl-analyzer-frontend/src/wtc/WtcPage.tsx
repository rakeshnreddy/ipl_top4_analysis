import { useEffect, useMemo, useState } from 'react';
import { ExternalLink } from 'lucide-react';
import '../App.css';
import './WtcPage.css';
import PageHeader, { type StatusTone } from '../components/PageHeader';
import { ErrorState, LoadingState } from '../components/PageState';
import SiteHeader from '../components/SiteHeader';
import { leagueHref, sportName, type LeagueIndex } from '../data/leagues';
import { formatGeneratedAt } from '../lib/standings';
import { appBaseHref, setJsonLd, setPageMeta } from '../lib/seo';
import { heatStyle, ordinalSuffix, readableOn, samePageHref, scrollToSection } from '../lib/ui';
import { formatChance } from '../sport/format';
import {
  formatPct,
  loadWtcData,
  type WtcNeed,
  type WtcNeedStatus,
  type WtcPayload,
  type WtcSeries,
  type WtcStanding,
  type WtcTest,
} from './wtcData';

const SECTIONS = ['table', 'needs', 'team', 'final', 'swing', 'series', 'positions', 'method'];

/** Test dates carry no time: format them as calendar days, whatever the reader's zone. */
const day = (value: string, options: Intl.DateTimeFormatOptions = { day: 'numeric', month: 'short' }) =>
  new Intl.DateTimeFormat(undefined, { ...options, timeZone: 'UTC' }).format(new Date(`${value}T00:00:00Z`));
const testDate = (test: { start: string; precision: 'day' | 'month' }) =>
  test.precision === 'month' ? `${day(test.start, { month: 'short', year: 'numeric' })}, date to be set` : day(test.start, { day: 'numeric', month: 'short', year: 'numeric' });
const longDay = (value: string) => day(value, { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });

const NEED_LABELS: Record<WtcNeedStatus, { label: string; tone: 'good' | 'accent' | 'warn' | 'bad' | 'muted' }> = {
  clinched: { label: 'Through to the final', tone: 'good' },
  'clinched-unless-level': { label: 'Through unless level', tone: 'good' },
  'in-control': { label: 'In control', tone: 'accent' },
  'needs-help': { label: 'Needs help', tone: 'warn' },
  'level-only': { label: 'Level at best', tone: 'warn' },
  eliminated: { label: 'Out of the race', tone: 'bad' },
  undetermined: { label: 'Still open', tone: 'muted' },
};

const isComplete = (payload: WtcPayload) => payload.metadata.season_status === 'complete';
const finalAhead = (payload: WtcPayload) => payload.metadata.season_status === 'playoffs';

function status(payload: WtcPayload, started: boolean): { label: string; tone: StatusTone } {
  if (isComplete(payload)) return { label: 'Final', tone: 'final' };
  if (finalAhead(payload)) return { label: 'Final ahead', tone: 'playoffs' };
  return started ? { label: 'In season', tone: 'live' } : { label: 'Pre-season', tone: 'pre-season' };
}

/** A simulated chance, unless the exact claims settle it: never 100% for an estimate, never "–" for a live chance. */
function finalChance(value: number, need: WtcNeed | undefined, complete: boolean) {
  if (complete || need?.status === 'clinched') return value >= 50 ? 'Through' : 'Out';
  if (need?.status === 'eliminated') return 'Out';
  if (value === 0) return '<0.1%';
  return formatChance(value);
}

function titleChance(value: number, need: WtcNeed | undefined, complete: boolean) {
  if (complete) return value >= 50 ? 'Champions' : '–';
  if (need?.status === 'eliminated') return 'Out';
  if (value === 0) return '<0.1%';
  return formatChance(value);
}

function seo(payload: WtcPayload) {
  const { shortName, seasonLabel, name } = payload.league;
  if (isComplete(payload)) {
    return {
      title: `${name} ${seasonLabel}: Final Table and Champions | Playoff Pulse`,
      description: `The final ${name} ${seasonLabel} points table, every series result and the final at ${payload.final.venue ?? 'the final venue'}.`,
    };
  }
  return {
    title: `${shortName} ${seasonLabel} Final & Title Odds: Points Table and What Each Team Needs | Playoff Pulse`,
    description: `${name} ${seasonLabel} points table (PCT), exact clinch and elimination checks, every series, and final and title odds from ${payload.analysis.simulations.toLocaleString()} simulated cycles.`,
  };
}

function teamKeyFromHash(payload: WtcPayload) {
  const match = window.location.hash.match(/^#team=(.+)$/);
  if (!match) return null;
  let wanted: string;
  try {
    wanted = decodeURIComponent(match[1]).toLowerCase();
  } catch {
    return null;
  }
  return payload.standings.find((row) => row.teamKey.toLowerCase() === wanted || row.shortName.toLowerCase() === wanted)?.teamKey ?? null;
}

/** The result of a Test in words, from the scoring side's point of view. */
function resultText(test: WtcTest, short: (key: string) => string) {
  const result = test.result;
  if (!result) {
    if (test.state === 'in_progress') return test.live ? `Under way: ${test.live}` : 'Under way · not counted yet';
    if (test.state === 'awaiting') return 'Result not in yet · simulated';
    if (test.state === 'cancelled') return 'Cancelled · not counted';
    if (test.state === 'postponed') return 'Postponed · not counted';
    return '';
  }
  switch (result.kind) {
    case 'host':
    case 'visitor':
      return `${short(result.winner ?? '')} won${result.margin ? ` by ${result.margin}` : ''}`;
    case 'draw':
      return 'Drawn';
    case 'tie':
      return 'Tied';
    case 'abandoned':
      return 'Abandoned · a draw';
    case 'unfit':
      return 'Abandoned, pitch unfit · visitors get the points';
    case 'awarded':
      return `Awarded to ${short(result.winner ?? '')}`;
    case 'forfeit':
      return `Forfeited · ${short(result.winner ?? '')} get the win`;
    default:
      return '';
  }
}

const TeamName = ({ team, label }: { team: { color: string; textColor: string; shortName: string; fullName: string } | undefined; label?: 'short' | 'full' }) => (
  <span className="wtc-name">
    <span aria-hidden="true" className="team-chip wtc-chip" style={team ? { backgroundColor: team.color } : undefined} />
    <strong>{label === 'full' ? team?.fullName : team?.shortName}</strong>
  </span>
);

/** An exact 0-100% bar: zero has no length, and the label sits outside the fill. */
const Bar = ({ value, label, tone = 'accent' }: { value: number; label: string; tone?: 'accent' | 'gold' | 'muted' }) => (
  <div className="wtc-bar">
    <span className="wtc-bar-track" aria-hidden="true">
      <span className={`wtc-bar-fill wtc-bar-${tone}`} style={{ width: `${Math.max(0, Math.min(100, value))}%` }} />
    </span>
    <span className="wtc-bar-label">{label}</span>
  </div>
);

/** Where a team's PCT can still end up, on a fixed 0-100% scale, with today's PCT marked. */
const PctRange = ({ row }: { row: WtcStanding }) => {
  if (row.worstPct === null || row.bestPct === null) return null;
  const low = Math.max(0, row.worstPct);
  const high = Math.max(0, row.bestPct);
  return (
    <div className="wtc-range" aria-hidden="true">
      <span className="wtc-range-track">
        <span className="wtc-range-span" style={{ left: `${low}%`, width: `${Math.max(high - low, 0)}%` }} />
        {row.pct !== null && <span className="wtc-range-now" style={{ left: `${Math.max(0, Math.min(100, row.pct))}%` }} />}
      </span>
      <span className="wtc-range-scale"><span>0%</span><span>100%</span></span>
    </div>
  );
};

const WtcPage = ({ leagueId, leagueIndex }: { leagueId: string; leagueIndex: LeagueIndex | null }) => {
  const [payload, setPayload] = useState<WtcPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [seriesFilter, setSeriesFilter] = useState<'all' | 'team'>('all');

  useEffect(() => {
    let active = true;
    loadWtcData(fetch, leagueId)
      .then((data) => active && setPayload(data))
      .catch((loadError: Error) => active && setError(loadError.message));
    return () => {
      active = false;
    };
  }, [leagueId]);

  useEffect(() => {
    if (!payload) return;
    const { title, description } = seo(payload);
    const pageHref = new URL(leagueHref(payload.league.id), window.location.origin).href;
    setPageMeta(title, description, pageHref);
    const baseHref = appBaseHref();
    setJsonLd({
      '@context': 'https://schema.org',
      '@graph': [
        { '@type': 'WebSite', '@id': `${baseHref}#website`, name: 'Playoff Pulse', url: baseHref },
        { '@type': 'WebPage', '@id': `${pageHref}#webpage`, name: title, description, url: pageHref, dateModified: payload.metadata.generated_at, isPartOf: { '@id': `${baseHref}#website` } },
        {
          '@type': 'Dataset',
          '@id': `${pageHref}#dataset`,
          name: title.split(' | ')[0],
          description,
          url: new URL(`${import.meta.env.BASE_URL}data/${payload.league.id}.json`, window.location.origin).href,
          dateModified: payload.metadata.generated_at,
          creator: { '@type': 'Organization', name: 'Playoff Pulse' },
          isBasedOn: payload.metadata.source_url,
        },
      ],
    });
  }, [payload]);

  useEffect(() => {
    if (!payload) return undefined;
    const sync = () => {
      const key = teamKeyFromHash(payload);
      if (key) {
        setSelectedKey(key);
        scrollToSection('team');
      } else if (SECTIONS.includes(window.location.hash.slice(1))) {
        scrollToSection(window.location.hash.slice(1));
      }
    };
    window.addEventListener('hashchange', sync);
    window.addEventListener('popstate', sync);
    sync();
    return () => {
      window.removeEventListener('hashchange', sync);
      window.removeEventListener('popstate', sync);
    };
  }, [payload]);

  const teams = useMemo(() => new Map((payload?.standings ?? []).map((row) => [row.teamKey, row])), [payload]);

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
  const short = (key: string) => teams.get(key)?.shortName ?? key;
  const chances = payload.analysis.probabilities;
  const needs = payload.analysis.needs;
  const selected = teams.get(selectedKey ?? '') ?? payload.standings[0];
  const finalists = payload.final.finalists;
  const champion = payload.playoffs?.champion ?? null;
  const joint = payload.playoffs?.jointChampions ?? null;
  const showTies = payload.standings.some((row) => row.tied > 0);
  const deducted = payload.league.deductions.reduce((sum, item) => sum + item.points, 0);
  const byFinal = [...payload.standings].sort((a, b) => (chances[b.teamKey]?.final ?? 0) - (chances[a.teamKey]?.final ?? 0));
  const titleFavourite = [...payload.standings].sort((a, b) => (chances[b.teamKey]?.title ?? 0) - (chances[a.teamKey]?.title ?? 0))[0];
  const likeliest = payload.final.matchups?.[0];

  const selectTeam = (key: string) => {
    setSelectedKey(key);
    window.history.replaceState(null, '', samePageHref(`#team=${encodeURIComponent(short(key))}`));
    scrollToSection('team');
    window.setTimeout(() => document.getElementById('team-title')?.focus({ preventScroll: true }), 0);
  };

  const facts = complete
    ? [
        { label: joint ? 'Joint champions' : 'Champions', value: joint ? joint.map(short).join(' & ') : champion ? teams.get(champion)?.fullName ?? champion : '–' },
        ...(payload.final.result?.margin && !joint ? [{ label: 'Final', value: `Won by ${payload.final.result.margin}` }] : []),
        { label: 'Table leader', value: payload.standings[0] ? `${payload.standings[0].shortName} ${formatPct(payload.standings[0].pct)}%` : '–' },
        { label: 'Latest update', value: formatGeneratedAt(payload.metadata.generated_at), testId: 'latest-update' },
      ]
    : [
        finalists
          ? { label: 'The final', value: `${short(finalists[0])} v ${short(finalists[1])}` }
          : likeliest
            ? { label: 'Likeliest final', value: `${likeliest.teams.map(short).join(' v ')} ${formatChance(likeliest.chance)}` }
            : { label: 'Final favourite', value: byFinal[0] ? `${byFinal[0].shortName} ${formatChance(chances[byFinal[0].teamKey].final)}` : '–' },
        { label: 'Title favourite', value: titleFavourite ? `${titleFavourite.shortName} ${formatChance(chances[titleFavourite.teamKey].title)}` : '–' },
        { label: 'Tests left', value: `${payload.league.testsLeft} of ${payload.league.testsTotal}` },
        { label: 'Latest update', value: formatGeneratedAt(payload.metadata.generated_at), testId: 'latest-update' },
      ];
  const sections = [
    { href: '#table', label: 'Table' },
    ...(!complete ? [{ href: '#needs', label: 'What they need' }] : []),
    { href: '#final', label: 'The final' },
    ...(payload.analysis.swing.length > 0 ? [{ href: '#swing', label: 'Swing Tests' }] : []),
    { href: '#series', label: 'Series' },
    ...(!complete ? [{ href: '#positions', label: 'Positions' }] : []),
    { href: '#method', label: 'How it works' },
  ];
  const strap = complete
    ? `The cycle is over: the final points table, every series and the final${payload.final.venue ? ` at ${payload.final.venue}` : ''}.`
    : finalAhead(payload)
      ? `The table is settled. ${finalists ? `${teams.get(finalists[0])?.fullName} play ${teams.get(finalists[1])?.fullName}` : 'The top two meet'} in the final${payload.final.venue ? ` at ${payload.final.venue}` : ''}${payload.final.start ? ` from ${day(payload.final.start)}` : ''}.`
      : started
        ? `${payload.league.testsLeft} Tests left before the table closes. The top two on percentage of points reach the final; odds from ${payload.analysis.simulations.toLocaleString()} simulated cycles.`
        : `Pre-cycle projections from ${payload.analysis.simulations.toLocaleString()} simulated cycles.`;
  const title = complete
    ? joint
      ? `${payload.league.shortName} ${payload.league.seasonLabel}: ${joint.map(short).join(' and ')} Share the Title`
      : `${payload.league.shortName} ${payload.league.seasonLabel}: ${champion ? teams.get(champion)?.fullName ?? champion : 'Final'} Are Champions`
    : `World Test Championship ${payload.league.seasonLabel} Odds`;

  const seriesShown = seriesFilter === 'team' ? payload.series.filter((item) => item.host === selected.teamKey || item.visitor === selected.teamKey) : payload.series;
  const seriesGroups: { key: string; label: string; items: WtcSeries[] }[] = [
    { key: 'in_progress', label: 'Under way', items: seriesShown.filter((item) => item.status === 'in_progress') },
    { key: 'scheduled', label: 'Still to play', items: seriesShown.filter((item) => item.status === 'scheduled') },
    { key: 'complete', label: 'Finished', items: [...seriesShown.filter((item) => item.status === 'complete' || item.status === 'cancelled')].reverse() },
  ].filter((group) => group.items.length > 0);

  return (
    <>
      <a className="skip-link" href={samePageHref('#main')}>Skip to content</a>
      <SiteHeader currentId={payload.league.id} currentLabel={`${payload.league.shortName} ${payload.league.seasonLabel}`} index={leagueIndex} />
      <main className="pulse-app wtc-page" data-testid="wtc-page" id="main">
        <PageHeader
          crumb={`${sportName(payload.league.sport)} · Test cricket · ${payload.league.shortName} ${payload.league.seasonLabel}`}
          facts={facts}
          factsLabel="Championship snapshot"
          sections={sections}
          status={status(payload, started)}
          strap={strap}
          title={title}
        />

        {payload.metadata.warnings.length > 0 && <p className="data-note" role="status">Data note: {payload.metadata.warnings.join(' ')}</p>}

        <section className="panel" id="table" aria-labelledby="table-title">
          <div className="section-heading">
            <h2 id="table-title">Points Table</h2>
            <p>{complete ? 'Final table' : 'Ranked by percentage of points (PCT)'}</p>
          </div>
          <div className="table-scroll" tabIndex={0} role="region" aria-label="Points table, scroll for all columns">
            <table className="data-table wtc-table">
              <caption className="visually-hidden">
                {payload.league.name} {payload.league.seasonLabel} points table{complete ? '' : ' with final and title odds'}
              </caption>
              <thead>
                <tr>
                  <th scope="col" className="col-rank"><abbr title="Position">#</abbr></th>
                  <th scope="col" className="col-team">Team</th>
                  <th scope="col"><abbr title="Matches played">M</abbr></th>
                  <th scope="col" className="col-optional"><abbr title="Won">W</abbr></th>
                  <th scope="col" className="col-optional"><abbr title="Lost">L</abbr></th>
                  <th scope="col" className="col-optional"><abbr title="Drawn (abandoned Tests count as drawn)">D</abbr></th>
                  {showTies && <th scope="col" className="col-optional"><abbr title="Tied">T</abbr></th>}
                  <th scope="col"><abbr title="Points deducted for slow over rates">Ded</abbr></th>
                  <th scope="col"><abbr title="Points, after deductions">Pts</abbr></th>
                  <th scope="col"><abbr title="Percentage of points">PCT</abbr></th>
                  <th scope="col" className="col-tier">{complete ? 'Final' : <abbr title="Reach the final (top two)">Final</abbr>}</th>
                  <th scope="col" className="col-tier">{complete ? 'Title' : <abbr title="Win the final outright">Title</abbr>}</th>
                </tr>
              </thead>
              <tbody>
                {payload.standings.map((row) => {
                  const need = needs[row.teamKey];
                  const odds = chances[row.teamKey];
                  const won = champion === row.teamKey || Boolean(joint?.includes(row.teamKey));
                  return (
                    <tr
                      className={`${row.rank <= payload.league.finalists ? 'zone-top' : ''}${row.rank === payload.league.finalists ? ' wtc-cut' : ''}${row.teamKey === selected.teamKey ? ' is-selected' : ''}`}
                      key={row.teamKey}
                      onClick={() => selectTeam(row.teamKey)}
                    >
                      <td className="col-rank">{row.rank}</td>
                      <th scope="row" className="col-team">
                        <button className="team-button" type="button" aria-pressed={row.teamKey === selected.teamKey} onClick={(event) => { event.stopPropagation(); selectTeam(row.teamKey); }}>
                          <span aria-hidden="true" className="team-chip" style={{ backgroundColor: row.color }} />
                          <strong>{row.shortName}</strong>
                          <small>{row.fullName}</small>
                        </button>
                      </th>
                      <td>{row.played}</td>
                      <td className="col-optional">{row.won}</td>
                      <td className="col-optional">{row.lost}</td>
                      <td className="col-optional">{row.drawn}</td>
                      {showTies && <td className="col-optional">{row.tied}</td>}
                      <td className={row.deducted ? 'wtc-deducted' : ''}>{row.deducted ? `−${row.deducted}` : 0}</td>
                      <td>{row.points}</td>
                      <td className="is-strong">{formatPct(row.pct)}</td>
                      <td className="col-tier" style={complete ? undefined : heatStyle(odds?.final ?? 0, 'good')}>
                        {complete ? (finalists?.includes(row.teamKey) ? <span className="mark-yes">✓<span className="visually-hidden"> Reached the final</span></span> : '–') : finalChance(odds?.final ?? 0, need, false)}
                      </td>
                      <td className="col-tier" style={complete ? undefined : heatStyle(odds?.title ?? 0, 'good')}>
                        {complete ? (won ? <span className="mark-yes">{joint ? 'Joint' : '✓'}<span className="visually-hidden"> Champions</span></span> : '–') : titleChance(odds?.title ?? 0, need, false)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <p className="probability-note">
            PCT is points after over-rate deductions divided by 12 points for every Test played: a win is worth {payload.league.points.win}, a tie {payload.league.points.tie}, a draw {payload.league.points.draw}. The line after {ordinalLabel(payload.league.finalists)} marks the final places. Teams level on PCT are split by {payload.league.tiebreakers.slice(1).map(lowerFirst).join(', then ')}.
            {!complete && ' Final and Title odds are simulated; "Out" and "Through" are exact.'} Narrow screens leave out the won, lost and drawn columns; each team's record is in its panel below.
          </p>
          {payload.metadata.notes.filter((note) => note.includes('level on')).map((note) => <p className="probability-note" key={note}>{note}</p>)}
          {payload.league.deductions.length > 0 && (
            <details className="wtc-deductions">
              <summary>Over-rate deductions: {deducted} points</summary>
              <ul>
                {payload.league.deductions.map((item) => (
                  <li key={`${item.team}-${item.test}`}>
                    <strong>{short(item.team)} −{item.points}</strong> · {item.note}{' '}
                    <a href={item.source} rel="noreferrer" target="_blank">ICC release<span className="visually-hidden">: {short(item.team)} lose {item.points} points</span><ExternalLink aria-hidden="true" size={12} /></a>
                  </li>
                ))}
              </ul>
            </details>
          )}
        </section>

        <TeamPanel payload={payload} row={selected} short={short} complete={complete} />

        {!complete && (
          <section className="panel" id="needs" aria-labelledby="needs-title">
            <div className="section-heading">
              <h2 id="needs-title">What Each Team Needs</h2>
              <p>Exact: every remaining result checked, ties included</p>
            </div>
            <ol className="wtc-needs">
              {payload.standings.map((row) => {
                const need = needs[row.teamKey];
                const label = NEED_LABELS[need?.status ?? 'undetermined'];
                return (
                  <li key={row.teamKey}>
                    <div className="wtc-need-head">
                      <a className="wtc-team-link" href={samePageHref(`#team=${encodeURIComponent(row.shortName)}`)}>
                        <TeamName team={row} /> <span className="wtc-need-full">{row.fullName}</span>
                      </a>
                      <span className={`wtc-pill wtc-pill-${label.tone}`}>{label.label}</span>
                    </div>
                    <p className="wtc-need-now">
                      {formatPct(row.pct)}% now · {row.testsLeft} Test{row.testsLeft === 1 ? '' : 's'} left
                    </p>
                    <PctRange row={row} />
                    <ul>
                      {(need?.statements ?? []).map((statement) => <li key={statement}>{statement}</li>)}
                    </ul>
                  </li>
                );
              })}
            </ol>
            <p className="probability-note">
              These statements look only at results. Over-rate deductions still to come could lower any team, so a team marked out can return only if teams above it lose points.
            </p>
          </section>
        )}

        <FinalPanel payload={payload} short={short} teams={teams} complete={complete} />

        {payload.analysis.swing.length > 0 && (
          <section className="panel" id="swing" aria-labelledby="swing-title">
            <div className="section-heading">
              <h2 id="swing-title">Tests That Swing the Race</h2>
              <p>The next Tests that move one team's final chance most</p>
            </div>
            <div className="wtc-swing-grid">
              {payload.analysis.swing.map((item) => (
                <article key={item.fixtureId}>
                  <span>{day(item.date)} · Test {item.number}</span>
                  <strong>{short(item.host)} v {short(item.visitor)}</strong>
                  <small>{short(item.team)}'s chance of reaching the final after each result</small>
                  <div className="wtc-swing-summary">
                    <strong>{item.swing.toFixed(1)} pp</strong>
                    <span>percentage-point swing</span>
                  </div>
                  <p className="wtc-scale-note">Chance scale: 0–100%</p>
                  <div className="wtc-swing-track" aria-hidden="true">
                    {(() => {
                      const values = [item.ifHost, item.ifDraw, item.ifVisitor].filter((value): value is number => typeof value === 'number');
                      const low = Math.min(...values);
                      return <span className="wtc-swing-range" style={{ left: `${low}%`, width: `${Math.max(...values) - low}%` }} />;
                    })()}
                    {[
                      { key: 'host', value: item.ifHost },
                      { key: 'draw', value: item.ifDraw },
                      { key: 'visitor', value: item.ifVisitor },
                    ].filter((point) => typeof point.value === 'number').map((point) => (
                      <span className={`wtc-swing-dot wtc-swing-${point.key}`} key={point.key} style={{ left: `${point.value}%` }} />
                    ))}
                  </div>
                  <dl>
                    <div><dt>{short(item.host)} win</dt><dd>{item.ifHost === null ? '–' : formatChance(item.ifHost)}</dd></div>
                    <div><dt>Draw</dt><dd>{item.ifDraw === null ? '–' : formatChance(item.ifDraw)}</dd></div>
                    <div><dt>{short(item.visitor)} win</dt><dd>{item.ifVisitor === null ? '–' : formatChance(item.ifVisitor)}</dd></div>
                  </dl>
                </article>
              ))}
            </div>
            <p className="probability-note">Each figure is the share of simulated cycles with that result in which the team reached the final. A result with too few simulations shows –.</p>
          </section>
        )}

        <section className="panel" id="series" aria-labelledby="series-title">
          <div className="section-heading">
            <h2 id="series-title">Series by Series</h2>
            <p>{payload.series.length} series, three at home and three away for each team</p>
          </div>
          <div className="wtc-filter" role="group" aria-label="Series shown">
            <button type="button" aria-pressed={seriesFilter === 'all'} onClick={() => setSeriesFilter('all')}>All series</button>
            <button type="button" aria-pressed={seriesFilter === 'team'} onClick={() => setSeriesFilter('team')}>{selected.fullName}'s series</button>
          </div>
          {seriesGroups.map((group) => {
            const list = (
              <div className="wtc-series-list">
                {group.items.map((item) => <SeriesCard item={item} key={item.id} short={short} teams={teams} />)}
              </div>
            );
            // Finished series of the whole cycle fold away; one team's six stay open.
            return group.key === 'complete' && seriesFilter === 'all' && !complete ? (
              <details className="wtc-series-group" key={group.key}>
                <summary>{group.label}: {group.items.length} series, latest first</summary>
                {list}
              </details>
            ) : (
              <div className="wtc-series-group" key={group.key}>
                <h3>{group.label}</h3>
                {list}
              </div>
            );
          })}
        </section>

        {!complete && (
          <section className="panel" id="positions" aria-labelledby="positions-title">
            <div className="section-heading">
              <h2 id="positions-title">Final Table Position Chances</h2>
              <p>Every team, every place, from the simulations</p>
            </div>
            <p className="probability-note" id="wtc-position-key">Each column is one exact final place, not a cumulative chance. – means no simulated finishes there.</p>
            <div className="table-scroll" tabIndex={0} role="region" aria-label="Final table position chances, scroll for all places" aria-describedby="wtc-position-key">
              <table className="data-table wtc-position-table">
                <caption className="visually-hidden">Chance of each final table place, percentages</caption>
                <thead>
                  <tr>
                    <th scope="col" className="col-team">Team</th>
                    {payload.standings.map((_, index) => <th scope="col" key={index}>{index + 1}{ordinalSuffix(index + 1)}</th>)}
                  </tr>
                </thead>
                <tbody>
                  {payload.standings.map((row) => (
                    <tr key={row.teamKey} onClick={() => selectTeam(row.teamKey)}>
                      <th scope="row" className="col-team"><TeamName team={row} /></th>
                      {(payload.analysis.positions[row.teamKey] ?? []).map((value, index) => (
                        <td key={index} style={heatStyle(value, 'good')} aria-label={`${row.shortName} ${index + 1}${ordinalSuffix(index + 1)}: ${value === 0 ? '0%' : formatChance(value)}`}>
                          {formatChance(value)}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        )}

        <section className="panel wtc-method" id="method" aria-labelledby="method-title">
          <div className="section-heading">
            <h2 id="method-title">How It Works</h2>
          </div>
          <ul>
            {payload.analysis.modelNotes.map((note) => <li key={note}>{note}</li>)}
            {payload.metadata.notes.filter((note) => !note.includes('level on')).map((note) => <li key={note}>{note}</li>)}
            <li>
              Tie-breakers, in order: {payload.league.tiebreakers.join('; ')}.
              {payload.league.rankings?.asOf && ` Until the window ends, the ranking used is the ICC's of ${payload.league.rankings.asOf}: ${payload.league.rankings.order.map(short).join(', ')}.`}
            </li>
            {payload.league.rules && (
              <li>
                Rules: {payload.league.rules.summary}{' '}
                {payload.league.rules.sources.map((source, index) => (
                  <span key={source.url}>
                    {index > 0 && ' · '}
                    <a href={source.url} rel="noreferrer" target="_blank">{source.label}</a>
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
          {!complete && payload.analysis.simulations > 0 && <> · {payload.analysis.simulations.toLocaleString()} simulations</>}
        </span>
        <a href={payload.metadata.source_url} target="_blank" rel="noreferrer">
          Results: {payload.metadata.source}{payload.metadata.license ? ` (Cricsheet data, ${payload.metadata.license})` : ''}
          <ExternalLink size={12} aria-hidden="true" />
        </a>
        {payload.metadata.license_url && (
          <a href={payload.metadata.license_url} target="_blank" rel="noreferrer">
            Licence: {payload.metadata.license}
            <ExternalLink size={12} aria-hidden="true" />
          </a>
        )}
        {payload.metadata.warnings.length > 0 && (
          <span className="footer-warning" data-testid="freshness-warning">Data note: {payload.metadata.warnings.join(' ')}</span>
        )}
      </footer>
    </>
  );
};

const ordinalLabel = (value: number) => `${value}${ordinalSuffix(value)}`;
/** "Series wins" mid-sentence, but "ICC" and "PCT" keep their capitals. */
const lowerFirst = (text: string) => (/^[A-Z][a-z]/.test(text) ? `${text[0].toLowerCase()}${text.slice(1)}` : text);

/** One series: the score, every Test with its result, points and deductions, or the odds of a Test to come. */
const SeriesCard = ({ item, short, teams }: { item: WtcSeries; short: (key: string) => string; teams: Map<string, WtcStanding> }) => {
  const host = teams.get(item.host);
  const visitor = teams.get(item.visitor);
  const draws = item.score.draws ?? 0;
  return (
    <article className="wtc-series" aria-labelledby={`series-${item.id}`}>
      <header>
        <h4 id={`series-${item.id}`}>
          <TeamName team={host} /> <span className="wtc-v">v</span> <TeamName team={visitor} />
        </h4>
        <p>
          {item.name} · {item.counted} Test{item.counted === 1 ? '' : 's'}
          {item.scheduled !== item.counted ? ` (${item.scheduled - item.counted} not counted)` : ''}
        </p>
        <p className="wtc-series-score">
          {item.status === 'scheduled'
            ? `From ${testDate(item.tests[0])}`
            : `${short(item.host)} ${item.score[item.host] ?? 0}–${item.score[item.visitor] ?? 0} ${short(item.visitor)}${draws ? ` · ${draws} drawn` : ''}${item.status === 'complete' ? (item.winner ? ` · ${short(item.winner)} won the series` : ' · series drawn') : ''}`}
        </p>
      </header>
      <ol>
        {item.tests.map((test) => {
          const points = test.result?.points;
          return (
            <li className={`wtc-test wtc-test-${test.state}`} key={test.key}>
              <span className="wtc-test-when">
                Test {test.number} · {testDate(test)}
                {test.tentative && test.precision === 'day' ? ' (provisional)' : ''}
              </span>
              <span className="wtc-test-where">
                {test.venue ?? 'Venue to be set'}
                {test.neutral ? ` · neutral ground in ${test.country}` : ''}
              </span>
              {test.state === 'scheduled' && test.odds ? (
                <span className="wtc-test-odds">
                  {short(item.host)} {formatChance(test.odds.host)} · draw {formatChance(test.odds.draw)} · {short(item.visitor)} {formatChance(test.odds.visitor)}
                </span>
              ) : (
                <span className="wtc-test-result">
                  {resultText(test, short)}
                  {points && <small> · points {short(item.host)} {points[item.host]}, {short(item.visitor)} {points[item.visitor]}</small>}
                </span>
              )}
              {test.deductions?.map((deduction) => (
                <small className="wtc-test-deduction" key={deduction.team}>
                  {short(deduction.team)} −{deduction.points} for slow over rate
                </small>
              ))}
            </li>
          );
        })}
      </ol>
      {item.note && <p className="wtc-series-note">{item.note}</p>}
    </article>
  );
};

/** The selected team: exact situation, odds and its own series. */
const TeamPanel = ({ payload, row, short, complete }: { payload: WtcPayload; row: WtcStanding; short: (key: string) => string; complete: boolean }) => {
  const need = payload.analysis.needs[row.teamKey];
  const odds = payload.analysis.probabilities[row.teamKey];
  const positions = payload.analysis.positions[row.teamKey] ?? [];
  const peak = Math.max(...positions, 0);
  const modal = positions.indexOf(peak) + 1;
  const next = payload.fixtures.filter((fixture) => fixture.host === row.teamKey || fixture.visitor === row.teamKey).slice(0, 6);
  return (
    <aside className="panel wtc-team-panel" id="team" aria-labelledby="team-title">
      <div className="spotlight-title">
        <span aria-hidden="true" className="team-badge" style={{ backgroundColor: row.color, color: readableOn(row.color, row.textColor) }}>{row.shortName}</span>
        <h2 id="team-title" tabIndex={-1}>{row.fullName}</h2>
      </div>
      <dl className="team-facts wtc-team-facts">
        <div><dt>Now</dt><dd>{row.rank}<small>{ordinalSuffix(row.rank)}</small> · {formatPct(row.pct)}%</dd></div>
        <div><dt>Record</dt><dd>{row.won}-{row.lost}-{row.drawn}{row.tied ? `-${row.tied}` : ''}{row.deducted ? ` · −${row.deducted} pts` : ''}</dd></div>
        <div><dt>Series won</dt><dd>{row.seriesWon} of {row.seriesPlayed}</dd></div>
        <div><dt>Away PCT</dt><dd>{formatPct(row.awayPct)}</dd></div>
        {!complete && <div><dt>Final</dt><dd>{finalChance(odds?.final ?? 0, need, false)}</dd></div>}
        {!complete && <div><dt>Title</dt><dd>{titleChance(odds?.title ?? 0, need, false)}{odds && odds.joint > 0 ? <small> +{formatChance(odds.joint)} joint</small> : null}</dd></div>}
      </dl>
      {!complete && need && (
        <div className="wtc-team-need">
          <h3>{NEED_LABELS[need.status].label}</h3>
          <ul>{need.statements.map((statement) => <li key={statement}>{statement}</li>)}</ul>
          {positions.length > 0 && peak > 0 && <p>Likeliest final place: {modal}{ordinalSuffix(modal)} ({formatChance(peak)} of simulations).</p>}
        </div>
      )}
      {next.length > 0 && (
        <div className="wtc-team-next">
          <h3>Tests left</h3>
          <ul>
            {next.map((fixture) => {
              const home = fixture.host === row.teamKey;
              const win = fixture.odds ? (home ? fixture.odds.host : fixture.odds.visitor) : null;
              const loss = fixture.odds ? (home ? fixture.odds.visitor : fixture.odds.host) : null;
              return (
                <li key={fixture.id}>
                  <span>{home ? 'v' : 'at'} <strong>{short(home ? fixture.visitor : fixture.host)}</strong> · {testDate(fixture)}{fixture.state === 'in_progress' ? ' · under way' : fixture.state === 'awaiting' ? ' · result not in yet' : ''}</span>
                  {fixture.odds && win !== null && loss !== null && (
                    <span className="wtc-outcome" aria-label={`Win ${formatChance(win)}, draw ${formatChance(fixture.odds.draw)}, lose ${formatChance(loss)}`}>
                      <span className="wtc-outcome-bar" aria-hidden="true">
                        <span style={{ width: `${win}%`, backgroundColor: row.color }} />
                        <span className="wtc-outcome-draw" style={{ width: `${fixture.odds.draw}%` }} />
                        <span className="wtc-outcome-loss" style={{ width: `${loss}%` }} />
                      </span>
                      <small>W {formatChance(win)} · D {formatChance(fixture.odds.draw)} · L {formatChance(loss)}</small>
                    </span>
                  )}
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </aside>
  );
};

/** The final: where and when, the rule for a draw, and the odds or the result. */
const FinalPanel = ({ payload, short, teams, complete }: { payload: WtcPayload; short: (key: string) => string; teams: Map<string, WtcStanding>; complete: boolean }) => {
  const final = payload.final;
  const chances = payload.analysis.probabilities;
  const contenders = [...payload.standings]
    .filter((row) => (chances[row.teamKey]?.final ?? 0) > 0)
    .sort((a, b) => (chances[b.teamKey]?.final ?? 0) - (chances[a.teamKey]?.final ?? 0));
  const when = final.start && final.end ? `${longDay(final.start)} to ${longDay(final.end)}` : 'Dates to be set';
  return (
    <section className="panel" id="final" aria-labelledby="final-title">
      <div className="section-heading">
        <h2 id="final-title">The Final</h2>
        <p>{[final.venue, final.city].filter(Boolean).join(', ') || 'Venue to be set'} · {when}</p>
      </div>
      <p className="wtc-final-rule">
        The top two at the end of the window meet over five days{final.reserveDay ? `, with a reserve day on ${longDay(final.reserveDay)}` : ', with a reserve day to be set'}. A drawn, tied or abandoned final makes both teams joint champions.
      </p>
      {complete && final.result && (
        <p className="wtc-final-result" role="status">
          {final.result.kind === 'joint' && final.result.joint
            ? `The final was ${final.result.margin || 'drawn'}: ${final.result.joint.map((key) => teams.get(key)?.fullName ?? key).join(' and ')} are joint champions.`
            : `${teams.get(final.result.winner ?? '')?.fullName ?? final.result.winner} won the final${final.result.margin ? ` by ${final.result.margin}` : ''}.`}
        </p>
      )}
      {!complete && final.live && (
        <p className="wtc-final-result wtc-final-live" role="status">The final is under way: {final.live}. The odds below are from before it started.</p>
      )}
      {!complete && final.finalists && final.odds && (
        <div className="wtc-final-odds">
          <h3>{short(final.finalists[0])} v {short(final.finalists[1])}</h3>
          <span className="wtc-outcome-bar wtc-final-bar" aria-hidden="true">
            <span style={{ width: `${final.odds[final.finalists[0]]}%`, backgroundColor: teams.get(final.finalists[0])?.color }} />
            <span className="wtc-outcome-draw" style={{ width: `${final.odds.draw}%` }} />
            <span style={{ width: `${final.odds[final.finalists[1]]}%`, backgroundColor: teams.get(final.finalists[1])?.color }} />
          </span>
          <dl>
            <div><dt>{short(final.finalists[0])} win</dt><dd>{formatChance(final.odds[final.finalists[0]])}</dd></div>
            <div><dt>Draw: joint champions</dt><dd>{formatChance(final.odds.draw)}</dd></div>
            <div><dt>{short(final.finalists[1])} win</dt><dd>{formatChance(final.odds[final.finalists[1]])}</dd></div>
          </dl>
        </div>
      )}
      {!complete && contenders.length > 0 && (
        <div className="table-scroll" tabIndex={0} role="region" aria-label="Final and title odds, scroll for all columns">
          <table className="data-table wtc-final-table">
            <caption className="visually-hidden">Chances of reaching the final, winning it outright and sharing the title</caption>
            <thead>
              <tr>
                <th scope="col" className="col-team">Team</th>
                <th scope="col">Reach the final</th>
                <th scope="col">Win it outright</th>
                <th scope="col">Share it (draw)</th>
              </tr>
            </thead>
            <tbody>
              {contenders.map((row) => {
                const value = chances[row.teamKey];
                const need = payload.analysis.needs[row.teamKey];
                return (
                  <tr key={row.teamKey}>
                    <th scope="row" className="col-team"><TeamName team={row} /></th>
                    <td><Bar value={need?.status === 'clinched' ? 100 : value.final} label={finalChance(value.final, need, false)} /></td>
                    <td><Bar value={value.title} label={titleChance(value.title, need, false)} tone="gold" /></td>
                    <td><Bar value={value.joint} label={value.joint === 0 ? '<0.1%' : formatChance(value.joint)} tone="muted" /></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
      {!complete && final.matchups && final.matchups.length > 0 && !final.finalists && (
        <div className="wtc-matchups">
          <h3>Likeliest finals</h3>
          <ol>
            {final.matchups.slice(0, 4).map((matchup) => (
              <li key={matchup.teams.join('-')}>
                <span>{matchup.teams.map(short).join(' v ')}</span>
                <Bar value={matchup.chance} label={formatChance(matchup.chance)} />
              </li>
            ))}
          </ol>
        </div>
      )}
      <p className="probability-note">
        The final is played in {final.country === 'ENG' ? 'England' : final.country}: England would be at home, any other pair on neutral ground. The model's draw chance is for a five-day Test; the reserve day is not modelled.
        {final.sources.map((source) => (
          <span key={source.url}> <a href={source.url} rel="noreferrer" target="_blank">{source.label}</a>.</span>
        ))}
      </p>
    </section>
  );
};

export default WtcPage;
