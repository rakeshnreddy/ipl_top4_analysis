import { useEffect, useMemo, useState } from 'react';
import { ExternalLink } from 'lucide-react';
import './App.css';
import {
  DEFAULT_LEAGUE_ID,
  isLeagueComplete,
  loadIplData,
  type FixtureImpact,
  type IplFixture,
  type IplPlayoffMatch,
  type IplSeasonPayload,
  type IplStanding,
  type QualificationPathResult,
  type QualificationTier,
} from './data/iplData';
import { leagueHref, type LeagueIndex } from './data/leagues';
import PageHeader from './components/PageHeader';
import { ErrorState, LoadingState } from './components/PageState';
import SiteHeader from './components/SiteHeader';
import { appBaseHref, setJsonLd, setPageMeta } from './lib/seo';
import { heatStyle, readableOn, scrollToSection } from './lib/ui';
import {
  formatGeneratedAt,
  formatNrr,
  formatPercent,
  hasNrr,
  raceSnapshot,
  rankingSort,
  setTeamPalette,
  teamColor,
  teamTextColor,
  tierProbability,
} from './lib/standings';
const DEFAULT_TIERS: QualificationTier[] = [
  { size: 4, label: 'Top 4' },
  { size: 2, label: 'Top 2' },
];
const SECTION_HASHES = new Set(['standings', 'top4', 'deep-dive', 'playoffs']);
const SHARE_KIT_HREF = `${import.meta.env.BASE_URL}share.html`;

const formatFixtureTime = (fixture: IplFixture) => {
  if (!fixture.dateTimeGMT) {
    return fixture.dateTimeLocal || 'Time TBA';
  }

  // The reader's own time zone: IPL fans see IST, BBL fans see their Australian time.
  return new Intl.DateTimeFormat(undefined, {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    timeZoneName: 'short',
  }).format(new Date(fixture.dateTimeGMT));
};

function maxPoints(payload: IplSeasonPayload, team: IplStanding) {
  return team.points + team.remainingMatches * (payload.league?.points?.win ?? 2);
}

function formatRecord(team: IplStanding) {
  const ties = team.ties ? `-${team.ties}T` : '';
  return `${team.wins}W-${team.losses}L${ties}-${team.noResult}NR`;
}

function tierLabel(payload: IplSeasonPayload, target: string) {
  const { playoffTier, topTier } = leagueInfo(payload);
  return [playoffTier, topTier].find((tier) => String(tier.size) === target)?.label ?? `Top ${target}`;
}

function teamShortName(payload: IplSeasonPayload, teamKey: string) {
  return payload.standings.find((team) => team.teamKey === teamKey)?.shortName || teamKey;
}

function ordinal(value: number) {
  const suffixes = ['th', 'st', 'nd', 'rd'];
  const lastTwo = value % 100;
  return `${value}${suffixes[(lastTwo - 20) % 10] || suffixes[lastTwo] || suffixes[0]}`;
}

const formatMatchDate = (value: string) =>
  new Intl.DateTimeFormat('en-IN', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' }).format(
    new Date(`${value}T00:00:00Z`),
  );

function finalSnapshot(payload: IplSeasonPayload) {
  const ordered = [...payload.standings].sort(rankingSort);
  const byKey = (key: string | null | undefined) => payload.standings.find((team) => team.teamKey === key) || null;
  return {
    ordered,
    champion: byKey(payload.playoffs?.champion),
    runnerUp: byKey(payload.playoffs?.runnerUp),
    finalMatch: payload.playoffs?.matches.find((match) => match.stage === 'Final') || null,
  };
}

/** League name, season and playoff format, with IPL defaults for older payloads. */
function leagueInfo(payload: IplSeasonPayload) {
  const league = payload.league;
  const [playoffTier, topTier] = league?.qualification?.length ? league.qualification : DEFAULT_TIERS;
  return {
    shortName: league?.shortName ?? 'IPL',
    seasonLabel: league?.seasonLabel ?? String(payload.metadata.season),
    playoffTier,
    topTier: topTier ?? playoffTier,
    secondChanceStages: league?.secondChanceStages ?? ['Qualifier 1'],
  };
}

/** Biggest climb and drop in playoff-tier chance since the previous update. */
function movementLeaders(payload: IplSeasonPayload) {
  if (!payload.movement) {
    return null;
  }
  const changes = Object.entries(payload.movement.changes);
  const riser = changes.filter(([, delta]) => delta > 0).sort((a, b) => b[1] - a[1])[0] ?? null;
  const faller = changes.filter(([, delta]) => delta < 0).sort((a, b) => a[1] - b[1])[0] ?? null;
  return { since: payload.movement.since, riser, faller };
}

/** The share kit only has IPL slides. */
function isIplLeague(payload: IplSeasonPayload) {
  return (payload.league?.shortName ?? 'IPL') === 'IPL';
}

function liveSeo(payload: IplSeasonPayload) {
  const { shortName, playoffTier, topTier } = leagueInfo(payload);
  return {
    title: `${shortName} ${playoffTier.label} Qualification Chances Today | ${shortName} Playoff Pulse`,
    description: `Daily ${shortName} ${playoffTier.label} and ${topTier.label} qualification probabilities, standings, cutline teams and team paths from ${shortName} Playoff Pulse.`,
  };
}

function finalSeo(payload: IplSeasonPayload) {
  const { shortName, seasonLabel } = leagueInfo(payload);
  return {
    title: `${shortName} ${seasonLabel} Final Standings, NRR & Playoff Results | ${shortName} Playoff Pulse`,
    description: `Final ${shortName} ${seasonLabel} points table with net run rate, playoff results and the champion, rebuilt from Cricsheet ball-by-ball data.`,
  };
}

function pointsGap(team: IplStanding, cutline: IplStanding) {
  const gap = cutline.points - team.points;
  if (gap === 0) {
    return `Level with ${cutline.shortName} on ${cutline.points} pts, out on NRR.`;
  }
  return `${ordinal(team.rank)} on ${team.points} pts, ${gap} pt${gap === 1 ? '' : 's'} behind ${cutline.shortName}.`;
}

function seasonOutcome(payload: IplSeasonPayload, team: IplStanding) {
  if (payload.playoffs?.champion === team.teamKey) {
    return 'Champions';
  }
  if (payload.playoffs?.runnerUp === team.teamKey) {
    return 'Runners-up';
  }
  // Some playoff losses are not exits: the IPL's Qualifier 1 loser still plays Qualifier 2.
  const { playoffTier, secondChanceStages } = leagueInfo(payload);
  const exits = (payload.playoffs?.matches || []).filter(
    (match) =>
      !secondChanceStages.includes(match.stage) &&
      match.winner !== null &&
      match.winner !== team.teamKey &&
      (match.teamA === team.teamKey || match.teamB === team.teamKey),
  );
  const exit = exits[exits.length - 1];
  if (exit) {
    return `Knocked out in ${exit.stage}`;
  }
  return team.rank <= playoffTier.size ? 'Reached the playoffs' : `Finished ${ordinal(team.rank)}`;
}

function teamKeyFromHash(payload: IplSeasonPayload) {
  const hash = window.location.hash.replace(/^#/, '');
  if (!hash.startsWith('team=')) {
    return null;
  }

  const requested = decodeURIComponent(hash.slice('team='.length)).trim().toLowerCase();
  if (!requested) {
    return null;
  }

  return (
    payload.standings.find(
      (team) =>
        team.teamKey.toLowerCase() === requested ||
        team.shortName.toLowerCase() === requested ||
        team.fullName.toLowerCase() === requested,
    )?.teamKey || null
  );
}

function sectionIdFromHash() {
  const hash = window.location.hash.replace(/^#/, '');
  return SECTION_HASHES.has(hash) ? hash : null;
}

function updateHash(value: string) {
  const nextUrl = `${window.location.pathname}${window.location.search}#${value}`;
  window.history.pushState(null, '', nextUrl);
}

function getPath(payload: IplSeasonPayload, teamKey: string, target: string): QualificationPathResult | null {
  return payload.analysis.qualificationPath[target]?.[teamKey] || null;
}

function pathSummary(path: QualificationPathResult | null, label: string) {
  if (!path) {
    return `No ${label} path data available.`;
  }

  const possible = typeof path.possible === 'number' ? `${path.possible}+ win(s) keeps it possible` : 'not alive in the exact model';
  const likely = typeof path.likely === 'number' ? `${path.likely}+ win(s) reaches 50%+` : 'no 50% path by own wins alone';
  const guaranteed = typeof path.guaranteed === 'number' ? `${path.guaranteed}+ win(s) guarantees it` : 'no own-win guarantee';

  return `${possible}; ${likely}; ${guaranteed}.`;
}

function pathShort(path: QualificationPathResult | null) {
  if (!path) {
    return 'Path unavailable';
  }

  const likely = typeof path.likely === 'number' ? `${path.likely}+ wins for 50%+` : 'No 50% path by own wins';
  const guaranteed = typeof path.guaranteed === 'number' ? `${path.guaranteed}+ wins locks it` : 'No own-win lock';
  return `${likely}; ${guaranteed}`;
}

function sortedImpacts(path: QualificationPathResult | null, limit = 6) {
  return [...(path?.fixtureImpacts || [])].sort((a, b) => b.impact - a.impact).slice(0, limit);
}

function oppositeResultLabel(payload: IplSeasonPayload, impact: FixtureImpact) {
  const otherWinner = impact.preferredWinner === impact.teamA ? impact.teamB : impact.teamA;
  const loser = impact.preferredWinner === impact.teamA ? impact.teamA : impact.teamB;
  return `${teamShortName(payload, otherWinner)} beat ${teamShortName(payload, loser)}`;
}

function practicalTakeaway(payload: IplSeasonPayload, team: IplStanding, path: QualificationPathResult | null) {
  const { playoffTier, topTier } = leagueInfo(payload);
  const chance = tierProbability(payload, team.teamKey, playoffTier.size);
  const likely = path?.likely;
  const guaranteed = path?.guaranteed;

  if (chance >= 90) {
    return `${team.shortName} can shift attention toward a ${topTier.label} finish.`;
  }
  if (chance >= 75) {
    return `${team.shortName} control most of the job if they avoid a late slide.`;
  }
  if (chance >= 55) {
    return `${team.shortName} are above the line, but the next wins still matter.`;
  }
  if (typeof likely === 'number') {
    return `${team.shortName} need at least ${likely} more win(s) to reach a 50% ${playoffTier.label} path.`;
  }
  if (typeof guaranteed === 'number') {
    return `${team.shortName} still have a route, but it depends on a clean finish and help.`;
  }
  return `${team.shortName} need wins and rival results immediately.`;
}

function setLeagueJsonLd(payload: IplSeasonPayload, pageHref: string, title: string, description: string) {
  const baseHref = appBaseHref();
  setJsonLd({
    '@context': 'https://schema.org',
    '@graph': [
      {
        '@type': 'WebSite',
        '@id': `${baseHref}#website`,
        name: 'Playoff Pulse',
        url: baseHref,
      },
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
        url: new URL(`${import.meta.env.BASE_URL}data/${payload.league?.id ?? DEFAULT_LEAGUE_ID}.json`, window.location.origin)
          .href,
        dateModified: payload.metadata.generated_at,
        creator: payload.metadata.source ? { '@type': 'Organization', name: payload.metadata.source } : undefined,
      },
    ],
  });
}

/** One cricket season's page; Root picks the league and loads the league list. */
function App({ leagueId, leagueIndex }: { leagueId: string; leagueIndex: LeagueIndex | null }) {
  const [payload, setPayload] = useState<IplSeasonPayload | null>(null);
  const homeLeagueId = leagueIndex?.default ?? DEFAULT_LEAGUE_ID;
  const [selectedTeamKey, setSelectedTeamKey] = useState<string>('');
  // Empty until the reader picks a tier; the league's playoff tier is the default.
  const [targetGoal, setTargetGoal] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    setLoading(true);

    loadIplData(fetch, leagueId)
      .then((data) => {
        if (!active) {
          return;
        }
        setTeamPalette(data.league?.teams);
        const sorted = [...data.standings].sort(rankingSort);
        setPayload(data);
        setSelectedTeamKey(teamKeyFromHash(data) || sorted[0]?.teamKey || '');
        setError(null);
      })
      .catch((fetchError: Error) => {
        if (active) {
          setError(fetchError.message);
        }
      })
      .finally(() => {
        if (active) {
          setLoading(false);
        }
      });

    return () => {
      active = false;
    };
  }, [leagueId]);

  useEffect(() => {
    if (!payload) {
      return undefined;
    }

    const syncTeamFromHash = () => {
      if (window.location.hash === '#reels') {
        // The Reels pack moved to its own page; keep old links working.
        window.location.replace(SHARE_KIT_HREF);
        return;
      }

      const hashTeam = teamKeyFromHash(payload);
      if (hashTeam) {
        setSelectedTeamKey(hashTeam);
        scrollToSection('deep-dive');
        return;
      }

      const sectionId = sectionIdFromHash();
      if (sectionId) {
        scrollToSection(sectionId);
      }
    };

    window.addEventListener('hashchange', syncTeamFromHash);
    window.addEventListener('popstate', syncTeamFromHash);
    syncTeamFromHash();

    return () => {
      window.removeEventListener('hashchange', syncTeamFromHash);
      window.removeEventListener('popstate', syncTeamFromHash);
    };
  }, [payload]);

  useEffect(() => {
    if (!payload) {
      return;
    }

    const { title, description } = isLeagueComplete(payload)
      ? finalSeo(payload)
      : liveSeo(payload);
    const pageHref = new URL(leagueHref(payload.league?.id ?? leagueId, homeLeagueId), window.location.origin).href;

    setPageMeta(title, description, pageHref);
    setLeagueJsonLd(payload, pageHref, title, description);
  }, [payload, leagueId, homeLeagueId]);

  const sortedStandings = useMemo(() => [...(payload?.standings || [])].sort(rankingSort), [payload]);
  const selectedTeam = useMemo(
    () => sortedStandings.find((team) => team.teamKey === selectedTeamKey) || sortedStandings[0],
    [selectedTeamKey, sortedStandings],
  );

  if (loading) {
    return <LoadingState />;
  }

  if (error || !payload || !selectedTeam) {
    return (
      <ErrorState
        homeHref={leagueId !== homeLeagueId ? import.meta.env.BASE_URL : undefined}
        message={error || 'The IPL payload is unavailable.'}
        title="Playoff Pulse could not load"
      />
    );
  }

  const { playoffTier, topTier } = leagueInfo(payload);
  const tiers = topTier.size === playoffTier.size ? [playoffTier] : [playoffTier, topTier];
  const goal = targetGoal || String(playoffTier.size);
  const seasonStarted = payload.standings.some((team) => team.matches > 0);
  const snapshot = raceSnapshot(payload, playoffTier.size);
  const playoffChance = tierProbability(payload, selectedTeam.teamKey, playoffTier.size);
  const topChance = tierProbability(payload, selectedTeam.teamKey, topTier.size);
  const playoffPath = getPath(payload, selectedTeam.teamKey, String(playoffTier.size));
  const topPath = getPath(payload, selectedTeam.teamKey, String(topTier.size));
  const selectedGoalPath = getPath(payload, selectedTeam.teamKey, goal);
  const sourceWarning = payload.metadata.data_freshness_status !== 'fresh' || payload.metadata.warnings.length > 0;
  const sourceIsStale = ['stale', 'invalid'].includes(payload.metadata.data_freshness_status.toLowerCase());
  const sourceWarningText = payload.metadata.warnings.join(' ') || `Freshness status: ${payload.metadata.data_freshness_status}.`;
  const isFinal = isLeagueComplete(payload);

  const handleTeamSelect = (team: IplStanding) => {
    setSelectedTeamKey(team.teamKey);
    updateHash(`team=${encodeURIComponent(team.shortName)}`);
    scrollToSection('deep-dive');
  };

  const { shortName, seasonLabel } = leagueInfo(payload);

  return (
    <>
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <SiteHeader currentId={payload.league?.id ?? leagueId} currentLabel={`${shortName} ${seasonLabel}`} index={leagueIndex} />
      <main className="pulse-app" data-testid="app-loaded" id="main">
        {isFinal ? (
          <FinalHero payload={payload} />
        ) : (
          <HeroSummary payload={payload} seasonStarted={seasonStarted} snapshot={snapshot} sourceIsStale={sourceIsStale} />
        )}

        <section className="race-grid" aria-label={isFinal ? 'IPL final standings and playoffs' : 'IPL playoff race board'}>
          <div className="ladder-panel" id="standings" data-testid="standings-ladder">
            <div className="section-heading">
              <h2>{isFinal ? 'Final Standings' : 'Standings'}</h2>
              <p>{isFinal ? 'Ranked by points, then net run rate' : 'Select a team to see its path'}</p>
            </div>

            <div className="table-scroll">
              <table className="data-table standings-table">
                <caption className="visually-hidden">
                  {shortName} {seasonLabel} standings
                </caption>
                <thead>
                  <tr>
                    <th className="col-rank" scope="col">
                      #
                    </th>
                    <th className="col-team" scope="col">
                      Team
                    </th>
                    <th className="col-optional" scope="col">
                      Record
                    </th>
                    <th scope="col">Pts</th>
                    <th scope="col">NRR</th>
                    <th className="col-optional" scope="col">
                      {isFinal ? 'Played' : 'Left'}
                    </th>
                    <th className="col-tier" scope="col">
                      {playoffTier.label}
                    </th>
                    <th className="col-tier" scope="col">
                      {topTier.label}
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {sortedStandings.map((team) => {
                    const inPlayoffZone = team.rank <= playoffTier.size;
                    const playoffOdds = tierProbability(payload, team.teamKey, playoffTier.size);
                    const topOdds = tierProbability(payload, team.teamKey, topTier.size);
                    const selected = selectedTeam.teamKey === team.teamKey;
                    return (
                      <tr
                        className={`standing-row ${inPlayoffZone ? 'zone-top' : ''} ${selected ? 'is-selected' : ''}`}
                        key={team.teamKey}
                        onClick={() => handleTeamSelect(team)}
                      >
                        <td className="col-rank">{team.rank}</td>
                        <th className="col-team" scope="row">
                          <button
                            aria-pressed={selected}
                            className="team-button"
                            onClick={(event) => {
                              event.stopPropagation();
                              handleTeamSelect(team);
                            }}
                            type="button"
                          >
                            <span aria-hidden="true" className="team-chip" style={{ backgroundColor: teamColor(team.teamKey) }} />
                            <strong>{team.shortName}</strong>
                            <small>{team.fullName}</small>
                          </button>
                        </th>
                        <td className="col-optional">{formatRecord(team)}</td>
                        <td className="is-strong">{team.points}</td>
                        <td className={hasNrr(team.nrr) ? (team.nrr >= 0 ? 'nrr-positive' : 'nrr-negative') : undefined}>
                          {formatNrr(team.nrr)}
                        </td>
                        <td className="col-optional">{isFinal ? team.matches : team.remainingMatches}</td>
                        {isFinal ? (
                          <>
                            <td className="col-tier">
                              <FinishMark achieved={inPlayoffZone} label={playoffTier.label} />
                            </td>
                            <td className="col-tier">
                              <FinishMark achieved={team.rank <= topTier.size} label={topTier.label} />
                            </td>
                          </>
                        ) : (
                          <>
                            <td className="col-tier" style={heatStyle(playoffOdds, 'good')}>
                              {formatPercent(playoffOdds)}
                            </td>
                            <td className="col-tier" style={heatStyle(topOdds, 'good')}>
                              {formatPercent(topOdds)}
                            </td>
                          </>
                        )}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>

          {isFinal ? (
            <PlayoffsPanel payload={payload} />
          ) : (
            <div className="probability-panel" id="top4" data-testid="probability-panel">
              <div className="section-heading">
                <h2>{playoffTier.label} Odds</h2>
                <p>Probabilities exclude NRR simulation</p>
              </div>

              <div className="race-bars">
                {sortedStandings.map((team) => {
                  const probability = tierProbability(payload, team.teamKey, playoffTier.size);
                  return (
                    <button
                      aria-pressed={selectedTeam.teamKey === team.teamKey}
                      className={`race-bar-row ${selectedTeam.teamKey === team.teamKey ? 'is-selected' : ''}`}
                      key={team.teamKey}
                      type="button"
                      onClick={() => handleTeamSelect(team)}
                    >
                      <span className="race-team">{team.shortName}</span>
                      <span aria-hidden="true" className="race-track">
                        <span
                          className="race-fill"
                          style={{ width: `${Math.max(probability, 2)}%`, backgroundColor: teamColor(team.teamKey) }}
                        />
                      </span>
                      <strong>{formatPercent(probability)}</strong>
                    </button>
                  );
                })}
              </div>

              <p className="probability-note">
                {seasonStarted
                  ? 'Equal points do not imply equal odds; the exact model also evaluates remaining fixtures and direct rival games.'
                  : 'Every team starts level; the odds move as results come in.'}
              </p>
            </div>
          )}
        </section>

        <section className="team-detail-panel spotlight-card" id="deep-dive" aria-label="Selected team detail">
          <div className="team-detail-header">
            <div className="spotlight-title">
              <span
                aria-hidden="true"
                className="team-badge"
                style={{
                  backgroundColor: teamColor(selectedTeam.teamKey),
                  color: readableOn(teamColor(selectedTeam.teamKey), teamTextColor(selectedTeam.teamKey)),
                }}
              >
                {selectedTeam.shortName}
              </span>
              <h2>{selectedTeam.fullName}</h2>
            </div>
            {!isFinal && (
              <div className="goal-tabs" role="group" aria-label="Select goal">
                {tiers.map((tier) => (
                  <button
                    aria-pressed={goal === String(tier.size)}
                    className={goal === String(tier.size) ? 'active' : ''}
                    key={tier.size}
                    onClick={() => setTargetGoal(String(tier.size))}
                    type="button"
                  >
                    {tier.label}
                  </button>
                ))}
              </div>
            )}
          </div>
        </section>

        {isFinal && <SeasonSummary payload={payload} />}
        {!isFinal && seasonStarted && <TodayRaceSummary payload={payload} snapshot={snapshot} />}

        {isFinal ? (
          <TeamSeasonCard payload={payload} team={selectedTeam} />
        ) : (
          <TeamDeepDive
            goalLabel={tierLabel(payload, goal)}
            path={selectedGoalPath}
            payload={payload}
            playoffChance={playoffChance}
            playoffPath={playoffPath}
            team={selectedTeam}
            topChance={topChance}
            topPath={topPath}
          />
        )}
      </main>

      <footer className="pulse-footer">
        <span>Model estimates for fans, not betting advice.</span>
        <span>
          Updated {formatGeneratedAt(payload.metadata.generated_at)} · {payload.analysis.method}
          {!isFinal && <> · {payload.analysis.simulationCount.toLocaleString()} scenarios</>}
        </span>
        <span>
          {isFinal
            ? 'Final table ranked by points, then net run rate.'
            : 'Current NRR is shown when available; scenario math excludes NRR swings.'}
        </span>
        <a href={payload.metadata.source_url} target="_blank" rel="noreferrer">
          Source: {payload.metadata.source}
          <ExternalLink size={12} aria-hidden="true" />
        </a>
        {isIplLeague(payload) && <a href={SHARE_KIT_HREF}>Share kit</a>}
        {payload.metadata.source_license && (
          <a href={payload.metadata.source_license_url || payload.metadata.source_url} target="_blank" rel="noreferrer">
            Licence: {payload.metadata.source_license}
            <ExternalLink size={12} aria-hidden="true" />
          </a>
        )}
        {sourceWarning && (
          <span className="footer-warning" data-testid="freshness-warning">
            Data note: {sourceWarningText}
          </span>
        )}
      </footer>
    </>
  );
}

const HeroSummary = ({
  payload,
  seasonStarted,
  snapshot,
  sourceIsStale,
}: {
  payload: IplSeasonPayload;
  seasonStarted: boolean;
  snapshot: ReturnType<typeof raceSnapshot>;
  sourceIsStale: boolean;
}) => {
  const { shortName, seasonLabel, playoffTier } = leagueInfo(payload);
  const chance = (team: IplStanding) => formatPercent(tierProbability(payload, team.teamKey, playoffTier.size));
  const opener = payload.fixtures[0];
  const facts = seasonStarted
    ? [
        { label: `Current ${playoffTier.label}`, value: snapshot.currentTop.map((team) => team.shortName).join(', ') },
        {
          label: 'Cutline team',
          value: snapshot.cutlineTeam ? `${snapshot.cutlineTeam.shortName} ${chance(snapshot.cutlineTeam)}` : 'Unavailable',
        },
        {
          label: 'Nearest challenger',
          value: snapshot.nearestChallenger
            ? `${snapshot.nearestChallenger.shortName} ${chance(snapshot.nearestChallenger)}`
            : 'Unavailable',
        },
      ]
    : [
        {
          label: 'Opening match',
          value: opener ? `${teamShortName(payload, opener.teamA)} vs ${teamShortName(payload, opener.teamB)}` : 'To be announced',
        },
        { label: 'First ball', value: opener ? formatFixtureTime(opener) : 'To be announced' },
        { label: 'Playoff places', value: `${playoffTier.size} of ${payload.standings.length} teams` },
      ];

  return (
    <>
      <PageHeader
        crumb={`Cricket · ${shortName} ${seasonLabel}`}
        facts={[
          ...facts,
          { label: 'Latest update', value: formatGeneratedAt(payload.metadata.generated_at), testId: 'latest-update' },
        ]}
        factsLabel="Race snapshot"
        sections={[
          { href: '#standings', label: 'Standings' },
          { href: '#top4', label: `${playoffTier.label} odds` },
          { href: '#deep-dive', label: 'Team path' },
          ...(isIplLeague(payload) ? [{ href: SHARE_KIT_HREF, label: 'Share kit' }] : []),
        ]}
        status={{ label: seasonStarted ? 'Live' : 'Pre-season', tone: seasonStarted ? 'live' : 'pre-season' }}
        strap="Updated daily after the night match"
        title={`${shortName} ${playoffTier.label} Qualification Probabilities`}
      />
      {sourceIsStale && <p className="stale-alert">Data freshness is marked {payload.metadata.data_freshness_status}.</p>}
    </>
  );
};

const TodayRaceSummary = ({
  payload,
  snapshot,
}: {
  payload: IplSeasonPayload;
  snapshot: ReturnType<typeof raceSnapshot>;
}) => {
  const { playoffTier } = leagueInfo(payload);
  const label = playoffTier.label;
  const moves = movementLeaders(payload);
  const moveNote = moves
    ? `${label} chance, percentage points since ${formatGeneratedAt(moves.since)}.`
    : 'Available after the next update.';
  const move = (entry: [string, number] | null | undefined) =>
    entry ? `${teamShortName(payload, entry[0])} ${entry[1] > 0 ? '+' : ''}${entry[1].toFixed(1)}` : 'No change';

  return (
    <section className="race-summary-panel" aria-labelledby="race-summary-title">
      <div className="section-heading">
        <h2 id="race-summary-title">Today&apos;s Race Summary</h2>
      </div>

      <div className="race-summary-grid">
        <article>
          <span>Current {label}</span>
          <strong>{snapshot.currentTop.map((team) => team.shortName).join(', ')}</strong>
        </article>
        <article>
          <span>Cutline team</span>
          <strong>{snapshot.cutlineTeam?.shortName || 'Unavailable'}</strong>
          {snapshot.cutlineTeam && (
            <small>
              {formatPercent(tierProbability(payload, snapshot.cutlineTeam.teamKey, playoffTier.size))} {label} chance
            </small>
          )}
        </article>
        <article>
          <span>Biggest {label} riser</span>
          <strong>{move(moves?.riser)}</strong>
          <small>{moveNote}</small>
        </article>
        <article>
          <span>Biggest {label} faller</span>
          <strong>{move(moves?.faller)}</strong>
          <small>{moveNote}</small>
        </article>
        <article>
          <span>Teams in danger</span>
          <strong>{snapshot.inDanger.map((team) => team.shortName).join(', ') || 'Unavailable'}</strong>
          <small>Lowest {label} odds inside the current {label.toLowerCase()}.</small>
        </article>
        <article>
          <span>Teams almost safe</span>
          <strong>{snapshot.almostSafe.map((team) => team.shortName).join(', ') || 'Unavailable'}</strong>
          <small>
            {snapshot.almostSafeIsFallback ? 'No team is at 90%; showing highest current odds.' : `At or above 90% ${label} chance.`}
          </small>
        </article>
      </div>
    </section>
  );
};

const FinishMark = ({ achieved, label }: { achieved: boolean; label: string }) => (
  <>
    <span aria-hidden="true" className={achieved ? 'mark-yes' : 'mark-no'}>
      {achieved ? '✓' : '–'}
    </span>
    <span className="visually-hidden">{achieved ? `Finished in the ${label}` : `Outside the ${label}`}</span>
  </>
);

const FinalHero = ({ payload }: { payload: IplSeasonPayload }) => {
  const { ordered, champion, runnerUp, finalMatch } = finalSnapshot(payload);
  const { shortName, seasonLabel, playoffTier } = leagueInfo(payload);
  // Who won leads; the season summary below covers the league stage.
  const facts = champion
    ? [
        { label: 'Champions', value: champion.shortName },
        ...(runnerUp ? [{ label: 'Runners-up', value: runnerUp.shortName }] : []),
      ]
    : [{ label: 'Still in the playoffs', value: ordered.slice(0, playoffTier.size).map((team) => team.shortName).join(', ') }];
  return (
    <PageHeader
      crumb={`Cricket · ${shortName} ${seasonLabel}`}
      facts={[...facts, { label: 'Latest update', value: formatGeneratedAt(payload.metadata.generated_at), testId: 'latest-update' }]}
      factsLabel="Season snapshot"
      sections={[
        { href: '#standings', label: 'Standings' },
        { href: '#playoffs', label: 'Playoffs' },
        { href: '#deep-dive', label: 'Team view' },
      ]}
      status={champion ? { label: 'Final', tone: 'final' } : { label: 'Playoffs', tone: 'playoffs' }}
      strap={
        champion
          ? `${champion.fullName} are champions${finalMatch ? `. Final: ${finalMatch.result}.` : '.'}`
          : 'The league stage is over and the playoffs are under way.'
      }
      title={`${shortName} ${seasonLabel} Final Standings`}
    />
  );
};

const SeasonSummary = ({ payload }: { payload: IplSeasonPayload }) => {
  const { ordered } = finalSnapshot(payload);
  const { playoffTier, topTier } = leagueInfo(payload);
  const leader = ordered[0];
  const cutline = ordered[playoffTier.size - 1];
  const firstOut = ordered[playoffTier.size];
  const bottom = ordered[ordered.length - 1];
  const topTeams = ordered.slice(0, topTier.size);
  const lastTopTeam = topTeams[topTeams.length - 1];
  const levelWithTop = ordered.slice(topTier.size).filter((team) => team.points === lastTopTeam.points);
  const leagueMatches = payload.standings.reduce((total, team) => total + team.matches, 0) / 2;

  return (
    <section className="race-summary-panel" aria-labelledby="season-summary-title">
      <div className="section-heading">
        <h2 id="season-summary-title">Season Summary</h2>
      </div>

      <div className="race-summary-grid">
        <article>
          <span>League stage winners</span>
          <strong>{leader.shortName}</strong>
          <small>{leader.points} pts · NRR {formatNrr(leader.nrr)}</small>
        </article>
        <article>
          <span>Playoff teams</span>
          <strong>{ordered.slice(0, playoffTier.size).map((team) => team.shortName).join(', ')}</strong>
          <small>
            {playoffTier.label} after {leagueMatches} league matches.
          </small>
        </article>
        <article>
          <span>{topTier.label} finish</span>
          <strong>{topTeams.map((team) => team.shortName).join(' & ')}</strong>
          <small>
            {levelWithTop.length > 0
              ? `${levelWithTop.map((team) => team.shortName).join(', ')} also reached ${lastTopTeam.points} pts but had a lower NRR.`
              : 'Settled on points.'}
          </small>
        </article>
        <article>
          <span>First team out</span>
          <strong>{firstOut?.shortName ?? 'None'}</strong>
          <small>{firstOut ? pointsGap(firstOut, cutline) : 'Every team reached the playoffs.'}</small>
        </article>
        <article>
          <span>Bottom of the table</span>
          <strong>{bottom.shortName}</strong>
          <small>{bottom.points} pts · NRR {formatNrr(bottom.nrr)}</small>
        </article>
      </div>
    </section>
  );
};

const PlayoffRow = ({ match, payload }: { match: IplPlayoffMatch; payload: IplSeasonPayload }) => (
  <li className={match.stage === 'Final' ? 'is-final' : undefined}>
    <span className="mini-label">{match.stage}</span>
    <span>
      {teamShortName(payload, match.teamA)} vs {teamShortName(payload, match.teamB)}
    </span>
    <strong>{match.result}</strong>
    <small>
      {formatMatchDate(match.date)}
      {match.venue ? ` · ${match.venue}` : ''}
    </small>
  </li>
);

const PlayoffsPanel = ({ payload }: { payload: IplSeasonPayload }) => {
  const matches = payload.playoffs?.matches || [];
  const { champion } = finalSnapshot(payload);
  const { shortName, seasonLabel } = leagueInfo(payload);
  return (
    <div className="probability-panel" id="playoffs" data-testid="playoffs-panel">
      <div className="section-heading">
        <h2>Playoffs</h2>
      </div>

      <ol className="fixture-list playoff-list">
        {matches.map((match) => (
          <PlayoffRow key={match.id} match={match} payload={payload} />
        ))}
        {matches.length === 0 && (
          <li>
            <span>No playoff results yet.</span>
            <small>Results appear here once the knockout matches are played.</small>
          </li>
        )}
      </ol>

      {champion && (
        <p className="probability-note">
          {champion.fullName} won the {shortName} {seasonLabel} title.
        </p>
      )}
    </div>
  );
};

const TeamSeasonCard = ({ payload, team }: { payload: IplSeasonPayload; team: IplStanding }) => {
  const { ordered } = finalSnapshot(payload);
  const { playoffTier } = leagueInfo(payload);
  const journey = (payload.playoffs?.matches || []).filter(
    (match) => match.teamA === team.teamKey || match.teamB === team.teamKey,
  );

  return (
    <div className="deep-dive-layout">
      <div className="deep-dive-grid">
        <article>
          <span className="mini-label">Season outcome</span>
          <strong>{seasonOutcome(payload, team)}</strong>
          <small>
            {team.rank <= playoffTier.size ? 'Qualified for the playoffs.' : pointsGap(team, ordered[playoffTier.size - 1])}
          </small>
        </article>
        <article>
          <span className="mini-label">Final position</span>
          <strong>
            #{team.rank} of {payload.standings.length}
          </strong>
          <small>
            {team.points} pts from {team.matches} matches
          </small>
        </article>
        <article>
          <span className="mini-label">Record</span>
          <strong>{formatRecord(team)}</strong>
          <small>
            {team.bonusPoints
              ? `League stage · ${team.bonusPoints} bonus point${team.bonusPoints === 1 ? '' : 's'}`
              : 'League stage'}
          </small>
        </article>
        <article>
          <span className="mini-label">Net run rate</span>
          <strong>{formatNrr(team.nrr)}</strong>
          <small>The tie-breaker after points.</small>
        </article>
      </div>

      <article className="deep-dive-section">
        <h3>Playoff journey</h3>
        <ul className="fixture-list">
          {journey.map((match) => (
            <li key={match.id}>
              <span>
                {match.stage}: {teamShortName(payload, match.teamA)} vs {teamShortName(payload, match.teamB)}
              </span>
              <small>
                {match.result} · {formatMatchDate(match.date)}
              </small>
            </li>
          ))}
          {journey.length === 0 && (
            <li>
              <span>Did not reach the playoffs.</span>
              <small>Finished {ordinal(team.rank)} in the league stage.</small>
            </li>
          )}
        </ul>
      </article>
    </div>
  );
};

const TeamDeepDive = ({
  goalLabel,
  path,
  payload,
  playoffChance,
  playoffPath,
  team,
  topChance,
  topPath,
}: {
  goalLabel: string;
  path: QualificationPathResult | null;
  payload: IplSeasonPayload;
  playoffChance: number;
  playoffPath: QualificationPathResult | null;
  team: IplStanding;
  topChance: number;
  topPath: QualificationPathResult | null;
}) => {
  const { playoffTier, topTier } = leagueInfo(payload);
  const ownFixtures = payload.fixtures
    .filter((fixture) => fixture.teamA === team.teamKey || fixture.teamB === team.teamKey)
    .slice(0, 5);
  const rivalImpacts = sortedImpacts(path, 6)
    .filter((impact) => impact.teamA !== team.teamKey && impact.teamB !== team.teamKey)
    .slice(0, 4);

  return (
    <div className="deep-dive-layout">
      <div className="deep-dive-grid">
        <article>
          <span className="mini-label">{playoffTier.label} chance</span>
          <strong>{formatPercent(playoffChance)}</strong>
          <small>{pathShort(playoffPath)}</small>
        </article>
        <article>
          <span className="mini-label">{topTier.label} chance</span>
          <strong>{formatPercent(topChance)}</strong>
          <small>{pathShort(topPath)}</small>
        </article>
        <article>
          <span className="mini-label">Points, rank, NRR</span>
          <strong>#{team.rank} · {team.points} pts · {formatNrr(team.nrr)}</strong>
          <small>
            {team.matches} played, {team.remainingMatches} left, max {maxPoints(payload, team)} pts
          </small>
        </article>
        <article>
          <span className="mini-label">What they need</span>
          <strong>{pathSummary(path, goalLabel)}</strong>
          <small>{goalLabel} model, excluding NRR simulation.</small>
        </article>
      </div>

      <div className="deep-dive-columns">
        <article className="deep-dive-section">
          <h3>Own fixtures</h3>
          <ul className="fixture-list">
            {ownFixtures.map((fixture) => {
              const opponentKey = fixture.teamA === team.teamKey ? fixture.teamB : fixture.teamA;
              return (
                <li key={fixture.id}>
                  <span>{team.shortName} vs {teamShortName(payload, opponentKey)}</span>
                  <small>{formatFixtureTime(fixture)} · {fixture.venue || 'Venue TBA'}</small>
                </li>
              );
            })}
            {ownFixtures.length === 0 && (
              <li>
                <span>No own fixtures listed.</span>
                <small>The current fixture feed does not list another match for {team.shortName}.</small>
              </li>
            )}
          </ul>
        </article>

        <article className="deep-dive-section">
          <h3>Rival results that help</h3>
          <ul className="impact-list compact-impact-list">
            {rivalImpacts.map((impact) => (
              <li key={`${team.teamKey}-${goalLabel}-help-${impact.fixtureId}`}>
                <strong>{impact.preferredLabel}</strong>
                <small>{impact.label} · adds {impact.impact.toFixed(1)} pts to {goalLabel} odds</small>
              </li>
            ))}
            {rivalImpacts.length === 0 && (
              <li>
                <strong>No clear rival swing.</strong>
                <small>The current model does not show a material neutral fixture dependency.</small>
              </li>
            )}
          </ul>
        </article>

        <article className="deep-dive-section">
          <h3>Rival results that hurt</h3>
          <ul className="impact-list compact-impact-list">
            {rivalImpacts.map((impact) => (
              <li key={`${team.teamKey}-${goalLabel}-hurt-${impact.fixtureId}`}>
                <strong>{oppositeResultLabel(payload, impact)}</strong>
                <small>{impact.label} · costs {impact.impact.toFixed(1)} pts versus preferred result</small>
              </li>
            ))}
            {rivalImpacts.length === 0 && (
              <li>
                <strong>No clear rival swing.</strong>
                <small>No material opposite result is available from this payload.</small>
              </li>
            )}
          </ul>
        </article>
      </div>

      <div className="deep-dive-bottom">
        <article className="deep-dive-section practical-takeaway">
          <h3>Practical takeaway</h3>
          <strong>{practicalTakeaway(payload, team, playoffPath)}</strong>
        </article>

        <div className="path-details">
          <h3>
            {team.shortName} {goalLabel} win buckets
          </h3>
          <div className="bucket-grid">
            {(path?.ownWinBuckets || []).map((bucket) => (
              <div className="bucket-cell" key={`${team.teamKey}-${goalLabel}-${bucket.wins}`}>
                <span>{bucket.wins}W</span>
                <strong>{formatPercent(bucket.probability)}</strong>
                <small>{bucket.scenarios.toLocaleString()} scenarios</small>
              </div>
            ))}
            {(path?.ownWinBuckets || []).length === 0 && (
              <div className="bucket-cell">
                <span>No buckets</span>
                <strong>Unavailable</strong>
                <small>No own-win bucket data in this payload.</small>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default App;
