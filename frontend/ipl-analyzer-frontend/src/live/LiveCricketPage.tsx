import { lazy, Suspense, useCallback, useEffect, useRef, useState } from 'react';
import { ArrowLeft, Clock3, Pause, Play, RefreshCw, Search, Radio, ChevronRight } from 'lucide-react';
import SiteHeader from '../components/SiteHeader';
import { liveCricketHref as cricketHref, type LeagueIndex } from '../data/leagues';
import { loadFreeDetail, loadFreeMatches } from '../data/freeCricket';
import { apiOrigin, parseDetailSnapshot, parseListSnapshot } from './client';
import { useLiveFeed } from './useLiveFeed';
import type { Bookmaker, Delivery, MatchDetailSnapshot, MatchSummary, Part, ScorecardInnings } from './types';
import './live.css';
const FieldGuide = lazy(() => import('./FieldGuide'));
const tabs = ['Summary', 'Scorecard', 'Commentary', 'Model win chance', 'Bookmaker odds', 'Field guide'] as const;
type Tab = typeof tabs[number];
const activeStates = new Set(['toss', 'live', 'innings-break', 'delayed', 'stumps', 'suspended']);
const stateName = (state: string) => ({
  'innings-break': 'Innings break',
  scheduled: 'Upcoming',
  toss: 'Toss',
  live: 'Live',
  delayed: 'Delayed',
  stumps: 'Stumps',
  suspended: 'Suspended',
  completed: 'Final',
  abandoned: 'Abandoned',
  unknown: 'Status unknown'
})[state] ?? state;
const matchId = () => new URLSearchParams(window.location.search).get('match');
const time = (value: string | null) => value ? new Date(value).toLocaleString(undefined, {
  month: 'short',
  day: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
  second: '2-digit',
  timeZoneName: 'short'
}) : 'Not supplied';
const old = (at: string | null, seconds: number, now: number) => !at || now - Date.parse(at) > seconds * 1000 || Date.parse(at) - now > 300_000;
const number = (value: number | null) => value === null ? '—' : value.toLocaleString();
const percentage = (value: number) => value > 0 && value < 0.001 ? '<0.1%' : value < 1 && value > 0.999 ? '>99.9%' : `${(value * 100).toFixed(1).replace(/\.0$/, '')}%`;
const score = (innings: MatchSummary['scores'][number]) => innings.display || (innings.runs === null ? 'Score unavailable' : `${innings.runs}${innings.wickets === null ? '' : `/${innings.wickets}`}`);
function Clocks({
  source,
  observedAt,
  fetchedAt,
  publishedAt
}: {
  source: string;
  observedAt: string | null;
  fetchedAt: string | null;
  publishedAt?: string | null;
}) {
  return <div className="lc-clocks">
  <span>{source}</span>
  {observedAt ? <span>Source event <time dateTime={observedAt}>{time(observedAt)}</time></span> : <span>Event time not supplied</span>}
  {publishedAt && <span>Feed published <time dateTime={publishedAt}>{time(publishedAt)}</time></span>}
  <span>Checked {fetchedAt ? <time dateTime={fetchedAt}>{time(fetchedAt)}</time> : 'Not yet'}</span>
  </div>;
}
function Unavailable({
  label,
  reason
}: {
  label: string;
  reason?: string | null;
}) {
  return <div className="lc-unavailable">
  <span className="lc-eyebrow">Unavailable</span>
  <h3>{label}</h3>
  <p>{reason || 'The current source does not supply this part of the match. Scores and other available views remain usable.'}</p>
  </div>;
}
function PartNotice({
  part,
  now,
  seconds
}: {
  part: Part<unknown>;
  now?: number;
  seconds?: number;
}) {
  const overdue = now !== undefined && seconds !== undefined && !!part.data && old(part.observedAt, seconds, now);
  return <>{(part.status !== 'available' || overdue) && <p className="lc-notice">{part.status === 'stale' || overdue ? 'Last known data · overdue' : part.status === 'error' ? 'Source error · last known data' : 'Unavailable'}{part.reason ? ` — ${part.reason}` : ''}</p>}<Clocks source={part.source} observedAt={part.observedAt} fetchedAt={part.fetchedAt} /></>;
}
function ScoreStrip({
  match,
  compact = false
}: {
  match: MatchSummary;
  compact?: boolean;
}) {
  return <div className={`lc-scores${compact ? ' lc-scores-compact' : ''}`}>
  {match.scores.length ? match.scores.map(innings => <div className="lc-innings" key={innings.id}>
    <div>
      <span>{innings.team}</span>
      <small>{innings.label}</small>
    </div>
    <div className="lc-score-number">
      <strong>{score(innings)}</strong>
      <span>{innings.overs !== null ? `${innings.overs} ov` : innings.legalBalls !== null ? `${innings.legalBalls} legal balls` : 'Overs unavailable'}</span>
    </div>
  </div>) : <p className="lc-muted">Innings scores have not been supplied.</p>}
  </div>;
}
function Scorecard({
  part,
  now,
  seconds
}: {
  part: Part<ScorecardInnings[]>;
  now: number;
  seconds: number;
}) {
  const [selected, setSelected] = useState('');
  const innings = part.data?.find(item => item.id === selected) ?? part.data?.[0];
  if (!innings) return <Unavailable label="Scorecard not supplied" reason={part.reason} />;
  return <><PartNotice part={part} now={now} seconds={seconds} /><label className="lc-field">Innings<select value={innings.id} onChange={event => setSelected(event.target.value)}>{part.data!.map(item => <option key={item.id} value={item.id}>{item.team} · {item.label}</option>)}</select></label><h3 className="lc-section-title">{innings.team} <span>{score(innings)} {innings.overs !== null ? `(${innings.overs} ov)` : ''}</span></h3><div className="lc-table-wrap" tabIndex={0} role="region" aria-label="Batting scorecard">
    <table>
      <caption>Batting · {innings.label}</caption>
      <thead>
        <tr>
          <th scope="col">Batter</th>
          <th scope="col">R</th>
          <th scope="col">B</th>
          <th scope="col">4s</th>
          <th scope="col">6s</th>
          <th scope="col">SR</th>
        </tr>
      </thead>
      <tbody>
        {innings.batting.map(batter => <tr key={batter.id}>
          <th scope="row">{batter.name}<small>{batter.dismissal ?? 'Dismissal not supplied'}</small></th>
          <td>{number(batter.runs)}</td>
          <td>{number(batter.balls)}</td>
          <td>{number(batter.fours)}</td>
          <td>{number(batter.sixes)}</td>
          <td>{number(batter.strikeRate)}</td>
        </tr>)}
      </tbody>
    </table>
    {!innings.batting.length && <p className="lc-table-empty">Batting details unavailable.</p>}
  </div>{innings.extras && <p className="lc-muted">Extras: {innings.extras}</p>}<div className="lc-table-wrap" tabIndex={0} role="region" aria-label="Bowling scorecard">
    <table>
      <caption>Bowling · {innings.label}</caption>
      <thead>
        <tr>
          <th scope="col">Bowler</th>
          <th scope="col">O</th>
          <th scope="col">M</th>
          <th scope="col">R</th>
          <th scope="col">W</th>
          <th scope="col">Econ</th>
        </tr>
      </thead>
      <tbody>
        {innings.bowling.map(bowler => <tr key={bowler.id}>
          <th scope="row">{bowler.name}</th>
          <td>{bowler.overs ?? '—'}</td>
          <td>{number(bowler.maidens)}</td>
          <td>{number(bowler.runs)}</td>
          <td>{number(bowler.wickets)}</td>
          <td>{number(bowler.economy)}</td>
        </tr>)}
      </tbody>
    </table>
    {!innings.bowling.length && <p className="lc-table-empty">Bowling details unavailable.</p>}
  </div>{innings.fallOfWickets.length > 0 && <p className="lc-muted">Fall of wickets: {innings.fallOfWickets.join(' · ')}</p>}{innings.partnerships.length > 0 && <p className="lc-muted">Partnerships: {innings.partnerships.join(' · ')}</p>}</>;
}
function Commentary({
  part,
  now,
  seconds
}: {
  part: Part<Delivery[]>;
  now: number;
  seconds: number;
}) {
  const [snapshot, setSnapshot] = useState(part);
  const shown = snapshot.data ?? [];
  const latest = part.data ?? [];
  const previous = new Map(shown.map(item => [item.id, item.revision]));
  const current = new Map(latest.map(item => [item.id, item.revision]));
  const changed = latest.filter(item => previous.get(item.id) !== item.revision).length + shown.filter(item => !current.has(item.id)).length;
  if (!part.data) return <Unavailable label="Ball-by-ball commentary not supplied" reason={part.reason} />;
  return <><PartNotice part={snapshot} now={now} seconds={seconds} /><p className="lc-muted">Deliveries stay in place while you read. Corrections replace the source event; they do not add a second ball.</p>{changed > 0 && <button className="lc-button lc-primary" type="button" onClick={() => setSnapshot(part)}>Show {changed} new or corrected {changed === 1 ? 'delivery' : 'deliveries'}</button>}<ol className="lc-deliveries">
    {[...shown].sort((a, b) => b.sequence - a.sequence).map(ball => <li key={ball.id}><div className="lc-ball">
        <strong>{ball.over || '—'}</strong>
        <small>{ball.innings}</small>
      </div><div>
        <p>{ball.text || 'Delivery details unavailable'}</p>
        {(ball.bowler || ball.batter) && <small>{ball.bowler ?? 'Bowler unknown'} to {ball.batter ?? 'Batter unknown'}</small>}
        <small>Source event {time(ball.observedAt)} · revision {ball.revision}</small>
      </div></li>)}
  </ol>{!shown.length && <p>No deliveries have been supplied.</p>}</>;
}
function Model({
  detail,
  now,
  interrupted
}: {
  detail: MatchDetailSnapshot;
  now: number;
  interrupted: boolean;
}) {
  const part = detail.model;
  const model = part.data;
  if (!model) return <Unavailable label="Match win model not available" reason={part.reason || 'Season qualification odds do not predict a live match. An in-play model will appear only after format-specific validation.'} />;
  if (interrupted) return <><Unavailable label="Current model estimate unavailable" reason="Connection interrupted. A fresh score revision is needed before showing a current estimate." /><PartNotice part={part} now={now} seconds={detail.staleAfterSeconds} /></>;
  const compatible = model.scoreRevision === detail.match.revision;
  const scoreOutdated = old(detail.match.observedAt ?? detail.generatedAt, detail.staleAfterSeconds, now);
  const outdated = part.status !== 'available'
    || scoreOutdated
    || old(model.predictedAt, detail.staleAfterSeconds, now)
    || (part.observedAt !== null && old(part.observedAt, detail.staleAfterSeconds, now));
  if (!compatible || outdated) return <><Unavailable label="Current model estimate unavailable" reason={!compatible ? 'The model uses an earlier score revision. Waiting for a matching calculation.' : scoreOutdated ? 'The parent score source is overdue. Waiting for a fresh score snapshot before showing a current estimate.' : 'The last model estimate is overdue. It is withheld from the current score view.'} /><PartNotice part={part} now={now} seconds={detail.staleAfterSeconds} /></>;
  return <><p className="lc-eyebrow">Model estimates · percentages</p><h3 className="lc-section-title">Chance of winning this match</h3><p className="lc-muted">{model.conditioning}</p><div className="lc-probabilities">
    {model.probabilities.map(item => <div key={item.outcome}>
      <div>
        <span>{item.outcome}</span>
        <strong>{percentage(item.probability)}</strong>
      </div>
      <div className="lc-probability-track">
        <span style={{
            width: `${item.probability * 100}%`
          }} />
      </div>
    </div>)}
  </div><p className="lc-muted">{model.modelId} · version {model.modelVersion} · calculated {time(model.predictedAt)} · input {model.scoreRevision}</p><PartNotice part={part} now={now} seconds={detail.staleAfterSeconds} />{model.history.length > 1 && <details>
    <summary>Recorded model estimates</summary>
    <div className="lc-table-wrap" tabIndex={0} role="region" aria-label="Model history">
      <table>
        <caption>Real saved estimates; gaps are not interpolated.</caption>
        <thead>
          <tr>
            <th scope="col">Calculated</th>
            <th scope="col">Outcomes</th>
          </tr>
        </thead>
        <tbody>
          {model.history.map(point => <tr key={`${point.scoreRevision}-${point.at}`}>
            <th scope="row">{time(point.at)}</th>
            <td>{point.probabilities.map(item => `${item.outcome}: ${percentage(item.probability)}`).join(' · ')}</td>
          </tr>)}
        </tbody>
      </table>
    </div>
  </details>}</>;
}
function Markets({
  part,
  seconds,
  now,
  paused,
  interrupted
}: {
  part: Part<Bookmaker[]>;
  seconds: number;
  now: number;
  paused: boolean;
  interrupted: boolean;
}) {
  const [book, setBook] = useState('all');
  if (!part.data?.length) return <Unavailable label="Bookmaker prices not supplied" reason={part.reason || 'No verified bookmaker feed is connected for this match. Decimal prices, bookmaker identity, settlement rules and quote times are required before display.'} />;
  return <><p className="lc-eyebrow">External bookmaker odds · decimal prices</p><h3 className="lc-section-title">Prices by bookmaker</h3><p className="lc-muted">Prices include bookmaker margin. They are separate from our model percentages. Only a verified open market with a current quote can be shown as current.</p><PartNotice part={part} now={now} seconds={seconds} /><label className="lc-field">Bookmaker<select value={book} onChange={event => setBook(event.target.value)}><option value="all">All bookmakers</option>{part.data.map(item => <option key={item.key} value={item.key}>{item.title}</option>)}</select></label>{part.data.filter(item => book === 'all' || item.key === book).map(bookmaker => <section className="lc-bookmaker" key={bookmaker.key}>
    <h4>{bookmaker.title}</h4>
    {bookmaker.markets.map(market => {
        const outdated = part.status !== 'available' || old(market.updatedAt ?? bookmaker.updatedAt ?? part.observedAt, seconds, now);
        const current = market.state === 'open' && !outdated && !paused && !interrupted;
        return <div className="lc-market" key={market.key}>
      <div className="lc-market-heading">
        <h5>{market.name}</h5>
        <span className={`lc-state ${current ? '' : 'lc-state-caution'}`}>{current ? 'Open' : interrupted ? `Connection interrupted · last state ${market.state}` : paused ? `Updates paused · last state ${market.state}` : outdated ? `Last quote · ${market.state} · overdue` : stateName(market.state)}</span>
      </div>
      <p className="lc-muted">Quote {time(market.updatedAt ?? bookmaker.updatedAt)} · {market.settlement ?? 'Settlement rules not supplied'}</p>
      <div className="lc-price-list">
        {market.outcomes.map(outcome => <div key={`${outcome.name}-${outcome.point ?? ''}`}>
          <span>{outcome.name}{outcome.point !== undefined ? ` (${outcome.point})` : ''}</span>
          <strong>{outcome.price.toFixed(2)}</strong>
          <small>{current ? 'Current quote' : 'Last quoted price · not current'}</small>
        </div>)}
      </div>
    </div>;
      })}
    {!bookmaker.markets.length && <p>Markets unavailable.</p>}
  </section>)}</>;
}
function MatchCenter({
  match,
  detail,
  loading,
  error,
  now,
  paused
}: {
  match: MatchSummary;
  detail: MatchDetailSnapshot | null;
  loading: boolean;
  error: string | null;
  now: number;
  paused: boolean;
}) {
  const [tab, setTab] = useState<Tab>('Summary');
  const tabRefs = useRef<(HTMLButtonElement | null)[]>([]);
  const label = match.teams.map(team => team.name).join(' v ') || 'Match';
  const scoreOverdue = detail && old(match.observedAt ?? detail.generatedAt, detail.staleAfterSeconds, now) && activeStates.has(match.state);
  return <article className="lc-center" aria-label="Match center">
  <header className="lc-match-header">
    <div className="lc-match-meta">
      <span className={`lc-state ${activeStates.has(match.state) ? 'lc-state-active' : ''}`}>{stateName(match.state)}</span>
      <span>{match.format} · {match.gender}</span>
    </div>
    <p className="lc-eyebrow">{match.competition.name}</p>
    <h2 id="lc-match-heading" tabIndex={-1}>{label}</h2>
    <ScoreStrip match={match} />
    <p className="visually-hidden" role="status" aria-live="polite" aria-atomic="true">{match.scores.map(innings => `${innings.team} ${score(innings)}, ${innings.overs ?? 'overs unavailable'}`).join('. ')}</p>
    {scoreOverdue && <p className="lc-notice">Score source overdue · displaying the last known score.</p>}
    <p className="lc-match-status" role="status">{match.statusText || 'Match status not supplied'}</p>
    <p className="lc-muted">{match.venue ?? 'Venue not supplied'} · {time(match.startTime)}</p>
    <Clocks source={match.source.name} observedAt={match.observedAt} fetchedAt={match.fetchedAt} publishedAt={detail?.generatedAt} />
  </header>
  {error && <p className="lc-notice" role="status">{error}</p>}
  <div className="lc-tabs" role="tablist" aria-label="Match views">
    {tabs.map((item, index) => <button key={item} id={`lc-tab-${index}`} ref={node => {
        tabRefs.current[index] = node;
      }} role="tab" type="button" aria-selected={tab === item} aria-controls="lc-panel" tabIndex={tab === item ? 0 : -1} onClick={() => setTab(item)} onKeyDown={event => {
        let next: number | undefined;
        if (event.key === 'ArrowRight') next = (index + 1) % tabs.length;
        if (event.key === 'ArrowLeft') next = (index - 1 + tabs.length) % tabs.length;
        if (event.key === 'Home') next = 0;
        if (event.key === 'End') next = tabs.length - 1;
        if (next !== undefined) {
          event.preventDefault();
          setTab(tabs[next]);
          tabRefs.current[next]?.focus();
        }
      }}>{item}</button>)}
  </div>
  <section id="lc-panel" className="lc-panel" role="tabpanel" aria-labelledby={`lc-tab-${tabs.indexOf(tab)}`} tabIndex={0}>
    {tab === 'Summary' ? <><h3 className="lc-section-title">Match summary</h3><p>{match.statusText || 'Waiting for the official match state.'}</p><dl className="lc-summary-facts">
        <div>
          <dt>Competition</dt>
          <dd>{match.competition.name}</dd>
        </div>
        <div>
          <dt>Format</dt>
          <dd>{match.format}</dd>
        </div>
        <div>
          <dt>Start</dt>
          <dd>{time(match.startTime)}</dd>
        </div>
        <div>
          <dt>Venue</dt>
          <dd>{match.venue ?? 'Not supplied'}</dd>
        </div>
      </dl><p className="lc-muted">Scores, detailed scorecards, commentary, model estimates and bookmaker prices have separate coverage and update times.</p><a className="lc-source-link" href={match.source.url} target="_blank" rel="noopener noreferrer">View score source <ChevronRight size={16} aria-hidden="true" /></a></> : tab === 'Field guide' ? <Suspense fallback={<p role="status">Loading field guide…</p>}><FieldGuide /></Suspense> : !detail ? <div className="lc-unavailable">
      <h3>{loading ? 'Loading match detail…' : 'Match detail unavailable'}</h3>
      <p>{error ?? 'Choose a covered match to see its available data.'}</p>
    </div> : tab === 'Scorecard' ? <Scorecard part={detail.scorecard} now={now} seconds={detail.staleAfterSeconds} /> : tab === 'Commentary' ? <Commentary part={detail.commentary} now={now} seconds={detail.staleAfterSeconds} /> : tab === 'Model win chance' ? <Model detail={detail} now={now} interrupted={!!error} /> : <Markets part={detail.markets} seconds={detail.staleAfterSeconds} now={now} paused={paused} interrupted={!!error} />}
  </section>
  </article>;
}
export default function LiveCricketPage({
  index = null
}: {
  index?: LeagueIndex | null;
}) {
  const [selected, setSelected] = useState(matchId);
  const [paused, setPaused] = useState(false);
  const [pausedAt, setPausedAt] = useState<string | null>(null);
  const [now, setNow] = useState(Date.now);
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState('live');
  const [format, setFormat] = useState('all');
  const [gender, setGender] = useState('all');
  const [competition, setCompetition] = useState('all');
  const order = useRef<string[]>([]);
  const rawOrigin = import.meta.env.VITE_LIVE_CRICKET_API_URL as unknown;
  const origin = apiOrigin(rawOrigin);
  const badConfiguration = !!rawOrigin && !origin;
  const free = !rawOrigin;
  const listPath = badConfiguration ? null : origin ? `${origin}/v1/matches` : 'free:matches';
  const list = useLiveFeed(listPath, parseListSnapshot, paused, free ? loadFreeMatches : undefined);
  const selectedSummary = list.data?.matches.find(match => match.id === selected);
  const detailParser = useCallback((value: unknown) => parseDetailSnapshot(value, selected ?? ''), [selected]);
  const detailPath = selected && !badConfiguration && (origin || selectedSummary) ? origin ? `${origin}/v1/matches/${encodeURIComponent(selected)}` : `free:match:${selected}` : null;
  const freeDetail = useCallback((signal: AbortSignal) => loadFreeDetail(selected!, selectedSummary!, signal), [selected, selectedSummary]);
  const detail = useLiveFeed(detailPath, detailParser, paused, free ? freeDetail : undefined);
  const match = detail.data?.match ?? selectedSummary;
  const focusedSelection = useRef<string | null>(null);
  const currentMatchId = match?.id;
  // Explicit navigation moves readers to the score; automatic refresh never moves focus.
  useEffect(() => {
    const target = selected
      ? currentMatchId === selected ? document.getElementById('lc-match-heading') : null
      : focusedSelection.current ? document.getElementById('lc-lobby-heading') : null;
    if (!target) return;
    target.focus({ preventScroll: true });
    const reveal = () => target.closest('.lc-center, .lc-lobby')?.scrollIntoView?.({ block: 'start', behavior: 'instant' });
    reveal();
    // History traversal restores its saved scroll after popstate. Reveal the focused
    // destination on the next frame as well, once that browser restoration is done.
    const frame = requestAnimationFrame(reveal);
    focusedSelection.current = selected;
    return () => cancelAnimationFrame(frame);
  }, [selected, currentMatchId]);
  useEffect(() => {
    const pop = () => setSelected(matchId());
    window.addEventListener('popstate', pop);
    return () => window.removeEventListener('popstate', pop);
  }, []);
  useEffect(() => {
    if (paused) return;
    const timer = setInterval(() => setNow(Date.now()), 30_000);
    return () => clearInterval(timer);
  }, [paused]);
  useEffect(() => {
    document.title = selected && match ? `${match.teams.map(team => team.shortName || team.name).join(' v ')} · Live Cricket · Playoff Pulse` : 'Live Cricket · Playoff Pulse';
  }, [selected, match]);
  const navigate = (id?: string) => {
    window.history.pushState({}, '', cricketHref(id));
    setSelected(id ?? null);
  };
  const togglePause = () => {
    const next = !paused;
    setPaused(next);
    setPausedAt(next ? new Date().toISOString() : null);
    if (!next) setNow(Date.now());
  };
  const matches = list.data?.matches ?? [];
  for (const item of matches) if (!order.current.includes(item.id)) order.current.push(item.id);
  const ordered = [...matches].sort((a, b) => order.current.indexOf(a.id) - order.current.indexOf(b.id));
  const filtered = ordered.filter(item => (status === 'all' || (status === 'live' ? activeStates.has(item.state) : status === 'upcoming' ? item.state === 'scheduled' : ['completed', 'abandoned'].includes(item.state))) && (format === 'all' || item.format === format) && (gender === 'all' || item.gender === gender) && (competition === 'all' || item.competition.id === competition) && `${item.teams.map(team => team.name).join(' ')} ${item.competition.name} ${item.venue ?? ''}`.toLowerCase().includes(search.trim().toLowerCase()));
  const formats = [...new Set(matches.map(item => item.format))].sort();
  const genders = [...new Set(matches.map(item => item.gender))].sort();
  const competitions = [...new Map(matches.map(item => [item.competition.id, item.competition])).values()].sort((a, b) => a.name.localeCompare(b.name));
  const stale = !!list.data && old(list.data.generatedAt, list.data.staleAfterSeconds, now);
  const coverageKnown = !!list.data && ['ok', 'partial'].includes(list.data.status);
  const groups = [...new Set(filtered.map(item => item.competition.id))];
  return <div className="live-cricket">
  <a className="skip-link" href={`${window.location.pathname}${window.location.search}#live-main`}>Skip to live cricket</a>
  <SiteHeader index={index} />
  <main className="lc-main" id="live-main">
    <header className={`lc-page-header${selected ? ' lc-header-selected' : ''}`}>
      <div>
        <p className="lc-eyebrow"><Radio size={16} aria-hidden="true" /> Cricket match center</p>
        <h1>Live Cricket</h1>
        <p>Scores first. Match probabilities and bookmaker prices, each with its own source.</p>
      </div>
      <div className="lc-controls">
        <button className="lc-button" onClick={togglePause} type="button" aria-pressed={paused}>{paused ? <Play size={16} aria-hidden="true" /> : <Pause size={16} aria-hidden="true" />}{paused ? 'Resume updates' : 'Pause updates'}</button>
        <button className="lc-button" onClick={() => {
            list.retry();
            detail.retry();
          }} disabled={paused || list.loading && detail.loading} type="button"><RefreshCw size={16} aria-hidden="true" />Refresh</button>
      </div>
    </header>
    <div className="lc-update-status" role="status">
      <Clock3 size={15} aria-hidden="true" />
      <span>{paused ? `Updates paused at ${time(pausedAt)}` : list.loading && !list.data ? 'Loading covered matches…' : list.error ? 'Connection interrupted · last verified data retained' : list.data?.status === 'unavailable' || list.data?.status === 'error' ? 'Source unavailable · coverage cannot be checked' : stale ? 'Feed publication overdue · last known data' : list.data ? `Automatic checks · about every ${list.data.refreshAfterSeconds}s while this tab is visible` : 'Connecting to match source…'}</span>
    </div>
    {badConfiguration && <div className="lc-notice" role="alert">Live data connection unavailable. The configured feed address is invalid. Coverage cannot be checked.</div>}
    {list.error && <div className="lc-notice" role="status">
      {list.error}
      <button type="button" className="lc-inline-button" disabled={paused} onClick={list.retry}>Try again</button>
    </div>}
    {list.data?.message && <p className="lc-coverage-note">{list.data.message}</p>}
    <div className={`lc-workspace${selected ? ' lc-has-match' : ''}`}>
      <aside className="lc-lobby" aria-label="Find a cricket match">
        <div className="lc-lobby-heading">
          <h2 id="lc-lobby-heading" tabIndex={-1}>Matches</h2>
          <span>{matches.length} covered</span>
        </div>
        <p className="lc-zone">Times in {Intl.DateTimeFormat().resolvedOptions().timeZone}</p>
        <div className="lc-status-filters" role="group" aria-label="Match status">
          {[['live', 'Live'], ['upcoming', 'Upcoming'], ['results', 'Results'], ['all', 'All']].map(([value, label]) => <button type="button" key={value} aria-pressed={status === value} onClick={() => setStatus(value)}>{label}</button>)}
        </div>
        <label className="lc-search"><span className="visually-hidden">Search teams, competition or venue</span><Search size={18} aria-hidden="true" /><input type="search" placeholder="Teams, competition, venue" value={search} onChange={event => setSearch(event.target.value)} /></label>
        <div className="lc-filter-grid">
          <label className="lc-field">Format<select value={format} onChange={event => setFormat(event.target.value)}><option value="all">All formats</option>{formats.map(value => <option key={value}>{value}</option>)}</select></label>
          <label className="lc-field">Category<select value={gender} onChange={event => setGender(event.target.value)}><option value="all">All categories</option>{genders.map(value => <option key={value}>{value}</option>)}</select></label>
          <label className="lc-field lc-filter-wide">Competition<select value={competition} onChange={event => setCompetition(event.target.value)}><option value="all">All competitions</option>{competitions.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
        </div>
        <div className="lc-match-list">
          {groups.map(id => <section className="lc-match-group" key={id}>
            <h3>{competitions.find(item => item.id === id)?.name}</h3>
            {filtered.filter(item => item.competition.id === id).map(item => <a className="lc-match-link" key={item.id} href={cricketHref(item.id)} aria-current={selected === item.id ? 'page' : undefined} onClick={event => {
                if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
                event.preventDefault();
                navigate(item.id);
              }}><div className="lc-list-meta">
                <span>{stateName(item.state)}</span>
                <span>{item.format} · {item.gender}</span>
              </div><strong>{item.teams.map(team => team.name).join(' v ') || 'Teams not supplied'}</strong><ScoreStrip match={item} compact /><p>{item.statusText || time(item.startTime)}</p></a>)}
          </section>)}
          {!filtered.length && !list.loading && <div className="lc-list-empty">
            <h3>{coverageKnown ? `No ${status === 'all' ? '' : `${status} `}matches in the current coverage.` : 'Match coverage cannot be checked.'}</h3>
            <p>{search || format !== 'all' || gender !== 'all' || competition !== 'all' ? 'Try clearing the search or filters.' : 'This describes the connected source, rather than every cricket match worldwide.'}</p>
            {status !== 'all' && <button className="lc-button" type="button" onClick={() => setStatus('all')}>View all covered matches</button>}
          </div>}
          {list.loading && !list.data && <div className="lc-loading" role="status">Loading match list…</div>}
        </div>
      </aside>
      <div className="lc-match-region">
        {selected && <a className="lc-back" href={cricketHref()} onClick={event => {
            if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
            event.preventDefault();
            navigate();
          }}><ArrowLeft size={18} aria-hidden="true" />All matches</a>}
        {match ? <MatchCenter key={match.id} match={match} detail={detail.data} loading={detail.loading} error={detail.error} now={now} paused={paused} /> : selected ? <div className="lc-selection-empty">
          <span className="lc-eyebrow">Match center</span>
          <h2>{list.loading || detail.loading ? 'Loading selected match…' : 'Match not in current coverage'}</h2>
          <p>{detail.error ?? 'The public match list is bounded. A match may leave this feed or no longer be supplied by the source.'}</p>
        </div> : <div className="lc-selection-empty">
          <div className="lc-crease" aria-hidden="true">
            <span />
            <i />
            <span />
          </div>
          <span className="lc-eyebrow">Follow the match</span>
          <h2>Choose a match.<br />Read the game.</h2>
          <p>Open a covered fixture to see its score, available scorecard and separate odds views.</p>
          <div className="lc-reading-key">
            <span><b>01</b> Match score</span>
            <span><b>02</b> Model win chance</span>
            <span><b>03</b> Bookmaker prices</span>
          </div>
        </div>}
      </div>
    </div>
    <section className="lc-coverage" aria-labelledby="lc-coverage-heading">
      <h2 id="lc-coverage-heading">Coverage & sources</h2>
      <p>{free ? 'The free public source covers a changing selection of competitions. Detailed innings, delivery commentary, calibrated match models and verified bookmaker prices may be unavailable. Coverage is shown field by field; this is not a complete worldwide fixture directory.' : 'The connected source defines which competitions and match fields are available. A missing match or data field does not imply no cricket is being played.'}</p>
      {list.data && <Clocks source={list.data.source.name} observedAt={null} fetchedAt={list.checkedAt} publishedAt={list.data.generatedAt} />}
      {!!list.data?.coverage.length && <details>
        <summary>Competition coverage</summary>
        <ul>
          {list.data.coverage.map(item => <li key={item.competition}><strong>{item.competition}</strong><span>Scores {item.scores ? 'available' : 'unavailable'} · Scorecard {item.scorecard ? 'available' : 'unavailable'} · Commentary {item.commentary ? 'available' : 'unavailable'} · Bookmaker prices {item.markets ? 'available' : 'unavailable'}</span>{item.note && <span>{item.note}</span>}</li>)}
        </ul>
      </details>}
      <a className="lc-attribution" href="https://sportscore.com/" target="_blank" rel="dofollow noopener" title="SportScore — live sports scores">Powered by SportScore</a>
    </section>
  </main>
  </div>;
}
