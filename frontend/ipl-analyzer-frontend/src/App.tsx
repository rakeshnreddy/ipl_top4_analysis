import { useEffect, useMemo, useState } from 'react';
import {
  AlertTriangle,
  CalendarClock,
  ExternalLink,
  Flame,
  ShieldCheck,
  Trophy,
  Zap,
} from 'lucide-react';
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
import { leagueHref, leagueIdFromLocation, loadLeagueIndex, type LeagueIndex } from './data/leagues';
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

function scrollToSection(sectionId: string) {
  window.setTimeout(() => {
    document.getElementById(sectionId)?.scrollIntoView?.({ block: 'start', behavior: 'smooth' });
  }, 0);
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

function appBaseHref() {
  return new URL(import.meta.env.BASE_URL, window.location.origin).href;
}

function setMetaTag(attribute: 'name' | 'property', key: string, content: string) {
  let element = document.head.querySelector<HTMLMetaElement>(`meta[${attribute}="${key}"]`);
  if (!element) {
    element = document.createElement('meta');
    element.setAttribute(attribute, key);
    document.head.appendChild(element);
  }
  element.content = content;
}

function setCanonical(href: string) {
  let element = document.head.querySelector<HTMLLinkElement>('link[rel="canonical"]');
  if (!element) {
    element = document.createElement('link');
    element.rel = 'canonical';
    document.head.appendChild(element);
  }
  element.href = href;
}

function setJsonLd(payload: IplSeasonPayload, pageHref: string, title: string, description: string) {
  const baseHref = appBaseHref();
  let script = document.head.querySelector<HTMLScriptElement>('script[data-ipl-jsonld="true"]');
  if (!script) {
    script = document.createElement('script');
    script.type = 'application/ld+json';
    script.dataset.iplJsonld = 'true';
    document.head.appendChild(script);
  }

  script.text = JSON.stringify({
    '@context': 'https://schema.org',
    '@graph': [
      {
        '@type': 'WebSite',
        '@id': `${baseHref}#website`,
        name: 'IPL Playoff Pulse',
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

function App() {
  const requestedLeague = useMemo(() => leagueIdFromLocation(), []);
  const [payload, setPayload] = useState<IplSeasonPayload | null>(null);
  const [leagueIndex, setLeagueIndex] = useState<LeagueIndex | null>(null);
  const [indexSettled, setIndexSettled] = useState(false);
  // The home page shows the index's default league (the newest IPL season); ?league= picks another.
  const homeLeagueId = leagueIndex?.default ?? DEFAULT_LEAGUE_ID;
  const leagueId = requestedLeague ?? (indexSettled ? homeLeagueId : null);
  const [selectedTeamKey, setSelectedTeamKey] = useState<string>('');
  // Empty until the reader picks a tier; the league's playoff tier is the default.
  const [targetGoal, setTargetGoal] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!leagueId) {
      return undefined;
    }
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
    let active = true;

    // The league switcher is optional; the page still works without the list.
    loadLeagueIndex()
      .then((index) => {
        if (active) {
          setLeagueIndex(index);
        }
      })
      .catch(() => {
        if (active) {
          setLeagueIndex(null);
        }
      })
      .finally(() => {
        if (active) {
          setIndexSettled(true);
        }
      });

    return () => {
      active = false;
    };
  }, []);

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
    const pageHref = new URL(leagueHref(payload.league?.id ?? leagueId ?? homeLeagueId, homeLeagueId), window.location.origin).href;

    document.title = title;
    setCanonical(pageHref);
    setMetaTag('name', 'description', description);
    setMetaTag('property', 'og:title', title);
    setMetaTag('property', 'og:description', description);
    setMetaTag('property', 'og:type', 'website');
    setMetaTag('property', 'og:url', pageHref);
    setMetaTag('name', 'twitter:card', 'summary');
    setMetaTag('name', 'twitter:title', title);
    setMetaTag('name', 'twitter:description', description);
    setJsonLd(payload, pageHref, title, description);
  }, [payload, leagueId, homeLeagueId]);

  const sortedStandings = useMemo(() => [...(payload?.standings || [])].sort(rankingSort), [payload]);
  const selectedTeam = useMemo(
    () => sortedStandings.find((team) => team.teamKey === selectedTeamKey) || sortedStandings[0],
    [selectedTeamKey, sortedStandings],
  );

  if (loading) {
    return (
      <main className="pulse-app pulse-center">
        <div className="loading-panel" role="status" aria-live="polite">
          <Flame aria-hidden="true" />
          <span>Loading IPL Playoff Pulse...</span>
        </div>
      </main>
    );
  }

  if (error || !payload || !selectedTeam) {
    return (
      <main className="pulse-app pulse-center">
        <section className="error-panel" role="alert">
          <AlertTriangle aria-hidden="true" />
          <h1>IPL Playoff Pulse could not load</h1>
          <p>{error || 'The IPL payload is unavailable.'}</p>
          {leagueId !== homeLeagueId && <a href={import.meta.env.BASE_URL}>Go to the IPL page</a>}
        </section>
      </main>
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

  return (
    <main className="pulse-app" data-testid="app-loaded">
      <LeagueSwitcher currentId={payload.league?.id ?? leagueId ?? homeLeagueId} index={leagueIndex} />

      {isFinal ? (
        <FinalHero payload={payload} />
      ) : (
        <HeroSummary payload={payload} seasonStarted={seasonStarted} snapshot={snapshot} sourceIsStale={sourceIsStale} />
      )}

      {isFinal && <SeasonSummary payload={payload} />}
      {!isFinal && seasonStarted && <TodayRaceSummary payload={payload} snapshot={snapshot} />}

      <section className="race-grid" aria-label={isFinal ? 'IPL final standings and playoffs' : 'IPL playoff race board'}>
        <div className="ladder-panel" id="standings" data-testid="standings-ladder">
          <div className="section-heading">
            <div>
              <h2>{isFinal ? 'Final Standings' : 'Standings'}</h2>
            </div>
            <ShieldCheck aria-hidden="true" />
          </div>

          <div className="standings-list">
            <div className="standing-header" aria-hidden="true">
              <span className="heading-rank">#</span>
              <span className="heading-stripe" />
              <span className="heading-team">Team</span>
              <span className="heading-record">Record</span>
              <span className="heading-points">Pts</span>
              <span className="heading-nrr">NRR</span>
              <span className="heading-left">{isFinal ? 'Played' : 'Left'}</span>
              <span className="heading-top4">{playoffTier.label}</span>
              <span className="heading-top2">{topTier.label}</span>
            </div>
            {sortedStandings.map((team) => {
              const inPlayoffZone = team.rank <= playoffTier.size;
              const playoffOdds = tierProbability(payload, team.teamKey, playoffTier.size);
              const topOdds = tierProbability(payload, team.teamKey, topTier.size);
              return (
                <div className="team-row-block" key={team.teamKey}>
                  <button
                    className={`standing-row ${inPlayoffZone ? 'is-playoff-zone' : ''} ${selectedTeam.teamKey === team.teamKey ? 'is-selected' : ''}`}
                    onClick={() => handleTeamSelect(team)}
                    type="button"
                  >
                    <span className="rank-pill">{team.rank}</span>
                    <span className="team-stripe" style={{ backgroundColor: teamColor(team.teamKey) }} />
                    <span className="team-name">
                      <strong>{team.shortName}</strong>
                      <small>{team.fullName}</small>
                    </span>
                    <span className="team-record">{formatRecord(team)}</span>
                    <span className="team-points">{team.points} pts</span>
                    <span className={`team-nrr ${hasNrr(team.nrr) ? (team.nrr >= 0 ? 'positive' : 'negative') : 'neutral'}`}>
                      {formatNrr(team.nrr)}
                    </span>
                    <span className="remaining">{isFinal ? team.matches : `${team.remainingMatches} left`}</span>
                    {isFinal ? (
                      <>
                        <FinishMark achieved={inPlayoffZone} className="top4-prob" label={playoffTier.label} />
                        <FinishMark achieved={team.rank <= topTier.size} className="top2-prob" label={topTier.label} />
                      </>
                    ) : (
                      <>
                        <span className="prob-mini top4-prob">{formatPercent(playoffOdds)}</span>
                        <span className="prob-mini top2-prob">{formatPercent(topOdds)}</span>
                      </>
                    )}
                  </button>
                </div>
              );
            })}
          </div>
        </div>

        {isFinal ? (
          <PlayoffsPanel payload={payload} />
        ) : (
          <div className="probability-panel" id="top4" data-testid="probability-panel">
            <div className="section-heading">
              <div>
                <span className="panel-kicker">Exact path lab</span>
                <h2>{playoffTier.label} Odds</h2>
              </div>
            </div>

            <div className="race-bars">
              {sortedStandings.map((team) => {
                const probability = tierProbability(payload, team.teamKey, playoffTier.size);
                return (
                  <button
                    className={`race-bar-row ${selectedTeam.teamKey === team.teamKey ? 'is-selected' : ''}`}
                    key={team.teamKey}
                    type="button"
                    onClick={() => handleTeamSelect(team)}
                  >
                    <span className="race-team">{team.shortName}</span>
                    <span className="race-track">
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
            <span style={{ backgroundColor: teamColor(selectedTeam.teamKey), color: teamTextColor(selectedTeam.teamKey) }}>
              {selectedTeam.shortName}
            </span>
            <div>
              <span className="panel-kicker">Selected team</span>
              <h2>{selectedTeam.fullName}</h2>
            </div>
          </div>
          {!isFinal && (
            <div className="goal-tabs" role="group" aria-label="Select goal">
              {tiers.map((tier) => (
                <button
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
      </section>

      <footer className="pulse-footer">
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
    </main>
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
  const { shortName, playoffTier } = leagueInfo(payload);
  const chance = (team: IplStanding) => formatPercent(tierProbability(payload, team.teamKey, playoffTier.size));
  const opener = payload.fixtures[0];

  return (
    <section className="hero-band compact-hero" aria-labelledby="page-title">
      <div className="hero-copy">
        <div className="hero-main">
          <span className="eyebrow">
            <Zap size={14} aria-hidden="true" />
            {shortName} Playoff Pulse
          </span>
          <h1 id="page-title">
            {shortName} {playoffTier.label} Qualification Probabilities
          </h1>
          <p>Updated daily after the night match</p>
          <nav className="quick-links" aria-label="Page sections">
            <a href="#standings">Standings</a>
            <a href="#top4">{playoffTier.label}</a>
            {isIplLeague(payload) && <a href={SHARE_KIT_HREF}>Share kit</a>}
            <a href="#deep-dive">Deep dive</a>
          </nav>
        </div>

        <div className="hero-facts" aria-label="Race snapshot">
          {seasonStarted ? (
            <>
              <div>
                <span>Current {playoffTier.label}</span>
                <strong>{snapshot.currentTop.map((team) => team.shortName).join(', ')}</strong>
              </div>
              <div>
                <span>Cutline team</span>
                <strong>
                  {snapshot.cutlineTeam ? `${snapshot.cutlineTeam.shortName} ${chance(snapshot.cutlineTeam)}` : 'Unavailable'}
                </strong>
              </div>
              <div>
                <span>Nearest challenger</span>
                <strong>
                  {snapshot.nearestChallenger
                    ? `${snapshot.nearestChallenger.shortName} ${chance(snapshot.nearestChallenger)}`
                    : 'Unavailable'}
                </strong>
              </div>
            </>
          ) : (
            <>
              <div>
                <span>Opening match</span>
                <strong>
                  {opener
                    ? `${teamShortName(payload, opener.teamA)} vs ${teamShortName(payload, opener.teamB)}`
                    : 'To be announced'}
                </strong>
              </div>
              <div>
                <span>First ball</span>
                <strong>{opener ? formatFixtureTime(opener) : 'To be announced'}</strong>
              </div>
              <div>
                <span>Playoff places</span>
                <strong>
                  {playoffTier.size} of {payload.standings.length} teams
                </strong>
              </div>
            </>
          )}
          <div>
            <span>Latest update</span>
            <strong data-testid="latest-update">{formatGeneratedAt(payload.metadata.generated_at)}</strong>
          </div>
        </div>

        <div className="hero-meta">
          <span>Source: {payload.metadata.source}</span>
          <span>{payload.analysis.method}</span>
          <span>Probabilities exclude NRR simulation</span>
        </div>
        {sourceIsStale && <p className="stale-alert">Data freshness is marked {payload.metadata.data_freshness_status}.</p>}
      </div>
    </section>
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
        <div>
          <span className="panel-kicker">Today&apos;s race summary</span>
          <h2 id="race-summary-title">Today&apos;s Race Summary</h2>
        </div>
        <ShieldCheck aria-hidden="true" />
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

const LeagueSwitcher = ({ currentId, index }: { currentId: string; index: LeagueIndex | null }) => {
  if (!index || index.leagues.length < 2) {
    return null;
  }

  return (
    <nav className="league-switcher" aria-label="Leagues">
      {index.leagues.map((league) => (
        <a
          aria-current={league.id === currentId ? 'page' : undefined}
          href={leagueHref(league.id, index.default)}
          key={league.id}
          title={league.name}
        >
          {league.shortName} {league.seasonLabel}
          {league.status !== 'complete' && <small>Live</small>}
        </a>
      ))}
    </nav>
  );
};

const FinishMark = ({ achieved, className, label }: { achieved: boolean; className: string; label: string }) => (
  <span
    className={`prob-mini ${className} ${achieved ? 'is-achieved' : 'is-missed'}`}
    title={`${achieved ? 'Finished' : 'Did not finish'} in the ${label}`}
  >
    {achieved ? '✓' : '–'}
  </span>
);

const FinalHero = ({ payload }: { payload: IplSeasonPayload }) => {
  const { ordered, champion, runnerUp } = finalSnapshot(payload);
  const { shortName, seasonLabel, playoffTier } = leagueInfo(payload);
  return (
    <section className="hero-band compact-hero" aria-labelledby="page-title">
      <div className="hero-copy">
        <div className="hero-main">
          <span className="eyebrow">
            <Trophy size={14} aria-hidden="true" />
            {shortName} Playoff Pulse
          </span>
          <h1 id="page-title">
            {shortName} {seasonLabel} Final Standings
          </h1>
          <p>
            {champion
              ? `Season complete · ${champion.fullName} are champions`
              : 'League stage complete · playoffs in progress'}
          </p>
          <nav className="quick-links" aria-label="Page sections">
            <a href="#standings">Standings</a>
            <a href="#playoffs">Playoffs</a>
            <a href="#deep-dive">Team view</a>
          </nav>
        </div>

        <div className="hero-facts" aria-label="Season snapshot">
          <div>
            <span>Champions</span>
            <strong>{champion?.shortName || 'To be decided'}</strong>
          </div>
          <div>
            <span>Runners-up</span>
            <strong>{runnerUp?.shortName || 'To be decided'}</strong>
          </div>
          <div>
            <span>Playoff teams</span>
            <strong>{ordered.slice(0, playoffTier.size).map((team) => team.shortName).join(', ')}</strong>
          </div>
          <div>
            <span>Latest update</span>
            <strong data-testid="latest-update">{formatGeneratedAt(payload.metadata.generated_at)}</strong>
          </div>
        </div>

        <div className="hero-meta">
          <span>Source: {payload.metadata.source}</span>
          <span>{payload.analysis.method}</span>
          <span>Ranked by points, then NRR</span>
        </div>
      </div>
    </section>
  );
};

const SeasonSummary = ({ payload }: { payload: IplSeasonPayload }) => {
  const { ordered, champion, finalMatch } = finalSnapshot(payload);
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
        <div>
          <span className="panel-kicker">Season recap</span>
          <h2 id="season-summary-title">Season Summary</h2>
        </div>
        <Trophy aria-hidden="true" />
      </div>

      <div className="race-summary-grid">
        <article>
          <span>Champions</span>
          <strong>{champion?.shortName || 'To be decided'}</strong>
          <small>{finalMatch ? `Final: ${finalMatch.result}.` : 'The playoffs are still in progress.'}</small>
        </article>
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
        <div>
          <span className="panel-kicker">Knockouts</span>
          <h2>Playoffs</h2>
        </div>
        <Trophy aria-hidden="true" />
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
        <h4>
          <Trophy size={15} aria-hidden="true" />
          Playoff journey
        </h4>
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
          <h4>
            <CalendarClock size={15} aria-hidden="true" />
            Own fixtures
          </h4>
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
          <h4>Rival results that help</h4>
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
          <h4>Rival results that hurt</h4>
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
          <h4>Practical takeaway</h4>
          <strong>{practicalTakeaway(payload, team, playoffPath)}</strong>
        </article>

        <div className="path-details">
          <h4>
            {team.shortName} {goalLabel} win buckets
          </h4>
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
