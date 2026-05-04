import { useEffect, useMemo, useState } from 'react';
import {
  AlertTriangle,
  CalendarClock,
  Check,
  Clipboard,
  Download,
  ExternalLink,
  Flame,
  ShieldCheck,
  Zap,
} from 'lucide-react';
import './App.css';
import {
  loadIplData,
  type FixtureImpact,
  type IplFixture,
  type IplSeasonPayload,
  type IplStanding,
  type QualificationPathResult,
} from './data/iplData';
import { loadReelsManifest, publicAssetUrl, type ReelsManifest, type ReelsSlide } from './data/reelsManifest';
import { team_styles } from './teamStyles';

type TargetGoal = '4' | '2';
type ShareKind = 'instagram' | 'x' | 'whatsapp';

const SEO_TITLE = 'IPL Top 4 Qualification Chances Today | IPL Playoff Pulse';
const SEO_DESCRIPTION =
  'Daily IPL Top 4 and Top 2 qualification probabilities, standings, cutline teams, team paths, and ready-to-share Reels slides from IPL Playoff Pulse.';
const SECTION_HASHES = new Set(['standings', 'top4', 'reels', 'deep-dive']);

const formatPercent = (value: number) =>
  `${value.toLocaleString(undefined, { maximumFractionDigits: value % 1 === 0 ? 0 : 1 })}%`;

const formatNrr = (value: number) => `${value >= 0 ? '+' : ''}${value.toFixed(3)}`;

const formatGeneratedAt = (value: string) =>
  new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value));

const formatGeneratedDate = (value: string) =>
  new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
  }).format(new Date(value));

const formatFixtureTime = (fixture: IplFixture) => {
  if (!fixture.dateTimeGMT) {
    return fixture.dateTimeLocal || 'Time TBA';
  }

  return new Intl.DateTimeFormat('en-IN', {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    timeZone: 'Asia/Kolkata',
    timeZoneName: 'short',
  }).format(new Date(fixture.dateTimeGMT));
};

const teamColor = (teamKey: string) => team_styles[teamKey]?.bg || '#2d405f';
const teamTextColor = (teamKey: string) => team_styles[teamKey]?.text || '#ffffff';

function rankingSort(a: IplStanding, b: IplStanding) {
  return b.points - a.points || b.nrr - a.nrr || b.wins - a.wins || a.fullName.localeCompare(b.fullName);
}

function maxPoints(team: IplStanding) {
  return team.points + team.remainingMatches * 2;
}

function targetLabel(target: TargetGoal) {
  return target === '4' ? 'Top 4' : 'Top 2';
}

function teamShortName(payload: IplSeasonPayload, teamKey: string) {
  return payload.standings.find((team) => team.teamKey === teamKey)?.shortName || teamKey;
}

function top4Probability(payload: IplSeasonPayload, teamKey: string) {
  return payload.analysis.overallProbabilities[teamKey]?.top4 ?? 0;
}

function top2Probability(payload: IplSeasonPayload, teamKey: string) {
  return payload.analysis.overallProbabilities[teamKey]?.top2 ?? 0;
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

function getPath(payload: IplSeasonPayload, teamKey: string, target: TargetGoal): QualificationPathResult | null {
  return payload.analysis.qualificationPath[target]?.[teamKey] || null;
}

function pathSummary(path: QualificationPathResult | null, target: TargetGoal) {
  if (!path) {
    return `No ${targetLabel(target)} path data available.`;
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

function raceSnapshot(payload: IplSeasonPayload) {
  const ordered = [...payload.standings].sort(rankingSort);
  const currentTopFour = ordered.slice(0, 4);
  const cutlineTeam = currentTopFour[3] || null;
  const nearestChallenger =
    [...ordered.slice(4)].sort((a, b) => top4Probability(payload, b.teamKey) - top4Probability(payload, a.teamKey))[0] ||
    ordered[4] ||
    null;
  const inDanger = [...currentTopFour]
    .sort((a, b) => top4Probability(payload, a.teamKey) - top4Probability(payload, b.teamKey))
    .slice(0, 2);
  const almostSafeByThreshold = ordered.filter((team) => top4Probability(payload, team.teamKey) >= 90);
  const almostSafe = almostSafeByThreshold.length > 0
    ? almostSafeByThreshold
    : [...ordered].sort((a, b) => top4Probability(payload, b.teamKey) - top4Probability(payload, a.teamKey)).slice(0, 2);

  return {
    ordered,
    currentTopFour,
    cutlineTeam,
    nearestChallenger,
    inDanger,
    almostSafe,
    almostSafeIsFallback: almostSafeByThreshold.length === 0,
  };
}

function shareTexts(payload: IplSeasonPayload): Record<ShareKind, string> {
  const snapshot = raceSnapshot(payload);
  const topFour = snapshot.currentTopFour.map((team) => team.shortName).join(', ');
  const cutline = snapshot.cutlineTeam
    ? `${snapshot.cutlineTeam.shortName} (${formatPercent(top4Probability(payload, snapshot.cutlineTeam.teamKey))})`
    : 'Unavailable';
  const challenger = snapshot.nearestChallenger
    ? `${snapshot.nearestChallenger.shortName} (${formatPercent(top4Probability(payload, snapshot.nearestChallenger.teamKey))})`
    : 'Unavailable';
  const date = formatGeneratedDate(payload.metadata.generated_at);

  return {
    instagram: `IPL Top 4 Qualification Probabilities - ${date}\n\nCurrent Top 4: ${topFour}\nCutline: ${cutline}\nNearest challenger: ${challenger}\n\nProbabilities exclude NRR simulation.\n#IPL2026 #IPLPlayoffs`,
    x: `IPL Top 4 chances today: ${topFour}. Cutline: ${cutline}. Nearest challenger: ${challenger}. Updated ${date}. Probabilities exclude NRR simulation.`,
    whatsapp: `IPL Playoff Pulse (${date})\nTop 4: ${topFour}\nCutline: ${cutline}\nNearest challenger: ${challenger}\nProbabilities exclude NRR simulation.`,
  };
}

function oppositeResultLabel(payload: IplSeasonPayload, impact: FixtureImpact) {
  const otherWinner = impact.preferredWinner === impact.teamA ? impact.teamB : impact.teamA;
  const loser = impact.preferredWinner === impact.teamA ? impact.teamA : impact.teamB;
  return `${teamShortName(payload, otherWinner)} beat ${teamShortName(payload, loser)}`;
}

function practicalTakeaway(payload: IplSeasonPayload, team: IplStanding, path: QualificationPathResult | null) {
  const chance = top4Probability(payload, team.teamKey);
  const likely = path?.likely;
  const guaranteed = path?.guaranteed;

  if (chance >= 90) {
    return `${team.shortName} can shift attention toward a Top 2 finish.`;
  }
  if (chance >= 75) {
    return `${team.shortName} control most of the job if they avoid a late slide.`;
  }
  if (chance >= 55) {
    return `${team.shortName} are above the line, but the next wins still matter.`;
  }
  if (typeof likely === 'number') {
    return `${team.shortName} need at least ${likely} more win(s) to reach a 50% Top 4 path.`;
  }
  if (typeof guaranteed === 'number') {
    return `${team.shortName} still have a route, but it depends on a clean finish and help.`;
  }
  return `${team.shortName} need wins and rival results immediately.`;
}

function appBaseHref() {
  return new URL(import.meta.env.BASE_URL, window.location.origin).href;
}

function absoluteAssetHref(path: string | null | undefined) {
  return path ? new URL(publicAssetUrl(path), window.location.origin).href : undefined;
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

function setJsonLd(payload: IplSeasonPayload, manifest: ReelsManifest | null) {
  const baseHref = appBaseHref();
  const imageUrl = absoluteAssetHref(manifest?.latestPreviewPath || manifest?.slides[0]?.path);
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
        '@id': `${baseHref}#webpage`,
        name: SEO_TITLE,
        description: SEO_DESCRIPTION,
        url: baseHref,
        dateModified: payload.metadata.generated_at,
        isPartOf: { '@id': `${baseHref}#website` },
        primaryImageOfPage: imageUrl ? { '@type': 'ImageObject', url: imageUrl, width: 1080, height: 1920 } : undefined,
      },
      {
        '@type': 'Dataset',
        '@id': `${baseHref}#dataset`,
        name: 'IPL 2026 Top 4 Qualification Probabilities',
        description: SEO_DESCRIPTION,
        url: new URL(`${import.meta.env.BASE_URL}data/ipl-2026.json`, window.location.origin).href,
        dateModified: payload.metadata.generated_at,
        creator: payload.metadata.source ? { '@type': 'Organization', name: payload.metadata.source } : undefined,
      },
    ],
  });
}

async function copyToClipboard(text: string) {
  try {
    await navigator.clipboard.writeText(text);
  } catch {
    const element = document.createElement('textarea');
    element.value = text;
    document.body.appendChild(element);
    element.select();
    document.execCommand('copy');
    document.body.removeChild(element);
  }
}

function raceCaption(payload: IplSeasonPayload) {
  const ordered = [...payload.standings].sort(rankingSort);
  const topFour = ordered.slice(0, 4).map((team) => team.shortName).join(', ');
  const chase = ordered.slice(4, 7).map((team) => team.shortName).join(', ');

  return `IPL 2026 Top 4 race: ${topFour} hold the playoff line right now. ${chase} are chasing. Exact all-combinations model, NRR shown for standings only. #IPL2026 #IPLPlayoffs`;
}

function drawRoundedRect(
  context: CanvasRenderingContext2D,
  x: number,
  y: number,
  width: number,
  height: number,
  radius: number,
) {
  context.beginPath();
  context.moveTo(x + radius, y);
  context.lineTo(x + width - radius, y);
  context.quadraticCurveTo(x + width, y, x + width, y + radius);
  context.lineTo(x + width, y + height - radius);
  context.quadraticCurveTo(x + width, y + height, x + width - radius, y + height);
  context.lineTo(x + radius, y + height);
  context.quadraticCurveTo(x, y + height, x, y + height - radius);
  context.lineTo(x, y + radius);
  context.quadraticCurveTo(x, y, x + radius, y);
  context.closePath();
}

async function exportRacePng(payload: IplSeasonPayload) {
  const teams = [...payload.standings].sort(rankingSort);
  const canvas = document.createElement('canvas');
  const width = 1080;
  const height = 1350;
  canvas.width = width;
  canvas.height = height;
  const context = canvas.getContext('2d');
  if (!context) {
    throw new Error('Canvas export is unavailable in this browser.');
  }

  const background = context.createLinearGradient(0, 0, width, height);
  background.addColorStop(0, '#0b1020');
  background.addColorStop(0.5, '#182036');
  background.addColorStop(1, '#24151b');
  context.fillStyle = background;
  context.fillRect(0, 0, width, height);

  context.fillStyle = 'rgba(255,255,255,0.09)';
  drawRoundedRect(context, 54, 54, 972, 1242, 34);
  context.fill();
  context.strokeStyle = 'rgba(255,255,255,0.2)';
  context.lineWidth = 2;
  context.stroke();

  context.fillStyle = '#facc15';
  context.font = '800 32px Inter, Arial, sans-serif';
  context.fillText('IPL PLAYOFF PULSE', 94, 122);
  context.fillStyle = '#ffffff';
  context.font = '900 84px Inter, Arial, sans-serif';
  context.fillText('Top 4 Odds', 94, 220);

  const y = 300;
  teams.forEach((team, index) => {
    const probability = payload.analysis.overallProbabilities[team.teamKey]?.top4 ?? 0;
    const rowHeight = 70;
    const rowY = y + index * 78;

    context.fillStyle = index < 4 ? 'rgba(255,255,255,0.14)' : 'rgba(255,255,255,0.08)';
    drawRoundedRect(context, 94, rowY, 892, rowHeight, 20);
    context.fill();

    context.fillStyle = teamColor(team.teamKey);
    drawRoundedRect(context, 116, rowY + 18, 34, 34, 17);
    context.fill();

    context.fillStyle = '#ffffff';
    context.font = '900 30px Inter, Arial, sans-serif';
    context.fillText(String(team.rank), 176, rowY + 43);
    context.fillText(team.shortName, 234, rowY + 43);

    context.fillStyle = 'rgba(255,255,255,0.62)';
    context.font = '700 22px Inter, Arial, sans-serif';
    context.fillText(`${team.points} pts  ${formatNrr(team.nrr)}`, 350, rowY + 43);

    context.fillStyle = 'rgba(255,255,255,0.18)';
    drawRoundedRect(context, 620, rowY + 24, 220, 18, 9);
    context.fill();

    context.fillStyle = teamColor(team.teamKey);
    drawRoundedRect(context, 620, rowY + 24, Math.max(8, probability * 2.2), 18, 9);
    context.fill();

    context.fillStyle = '#ffffff';
    context.font = '900 30px Inter, Arial, sans-serif';
    context.fillText(formatPercent(probability), 858, rowY + 45);
  });

  context.fillStyle = 'rgba(255,255,255,0.58)';
  context.font = '600 22px Inter, Arial, sans-serif';
  context.fillText(formatGeneratedDate(payload.metadata.generated_at), 94, 1252);

  const blob = await new Promise<Blob>((resolve, reject) => {
    canvas.toBlob((value) => {
      if (value) {
        resolve(value);
      } else {
        reject(new Error('Could not create PNG.'));
      }
    }, 'image/png');
  });

  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = 'ipl-playoff-pulse-top4-race.png';
  link.click();
  URL.revokeObjectURL(url);
}

function App() {
  const [payload, setPayload] = useState<IplSeasonPayload | null>(null);
  const [reelsManifest, setReelsManifest] = useState<ReelsManifest | null>(null);
  const [selectedTeamKey, setSelectedTeamKey] = useState<string>('');
  const [targetGoal, setTargetGoal] = useState<TargetGoal>('4');
  const [copiedCaption, setCopiedCaption] = useState(false);
  const [copiedShare, setCopiedShare] = useState<ShareKind | null>(null);
  const [exportingRace, setExportingRace] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reelsError, setReelsError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    setLoading(true);

    loadIplData()
      .then((data) => {
        if (!active) {
          return;
        }
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
  }, []);

  useEffect(() => {
    let active = true;

    loadReelsManifest()
      .then((manifest) => {
        if (active) {
          setReelsManifest(manifest);
          setReelsError(null);
        }
      })
      .catch((fetchError: Error) => {
        if (active) {
          setReelsError(fetchError.message);
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

    const baseHref = appBaseHref();
    const preview = absoluteAssetHref(reelsManifest?.latestPreviewPath || reelsManifest?.slides[0]?.path);

    document.title = SEO_TITLE;
    setCanonical(baseHref);
    setMetaTag('name', 'description', SEO_DESCRIPTION);
    setMetaTag('property', 'og:title', SEO_TITLE);
    setMetaTag('property', 'og:description', SEO_DESCRIPTION);
    setMetaTag('property', 'og:type', 'website');
    setMetaTag('property', 'og:url', baseHref);
    setMetaTag('name', 'twitter:card', 'summary_large_image');
    setMetaTag('name', 'twitter:title', SEO_TITLE);
    setMetaTag('name', 'twitter:description', SEO_DESCRIPTION);
    if (preview) {
      setMetaTag('property', 'og:image', preview);
      setMetaTag('name', 'twitter:image', preview);
    }
    setJsonLd(payload, reelsManifest);
  }, [payload, reelsManifest]);

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
        </section>
      </main>
    );
  }

  const snapshot = raceSnapshot(payload);
  const topFourProbability = top4Probability(payload, selectedTeam.teamKey);
  const topTwoProbability = top2Probability(payload, selectedTeam.teamKey);
  const selectedTop4Path = getPath(payload, selectedTeam.teamKey, '4');
  const selectedTop2Path = getPath(payload, selectedTeam.teamKey, '2');
  const selectedGoalPath = getPath(payload, selectedTeam.teamKey, targetGoal);
  const sourceWarning = payload.metadata.data_freshness_status !== 'fresh' || payload.metadata.warnings.length > 0;
  const sourceIsStale = ['stale', 'invalid'].includes(payload.metadata.data_freshness_status.toLowerCase());
  const sourceWarningText = payload.metadata.warnings.join(' ') || `Freshness status: ${payload.metadata.data_freshness_status}.`;
  const shareTextMap = shareTexts(payload);
  const latestPackHref = `${appBaseHref()}#reels`;

  const handleTeamSelect = (team: IplStanding) => {
    setSelectedTeamKey(team.teamKey);
    updateHash(`team=${encodeURIComponent(team.shortName)}`);
    scrollToSection('deep-dive');
  };

  const handleCopyCaption = async () => {
    await copyToClipboard(raceCaption(payload));
    setCopiedCaption(true);
    window.setTimeout(() => setCopiedCaption(false), 1600);
  };

  const handleCopyShare = async (kind: ShareKind) => {
    await copyToClipboard(shareTextMap[kind]);
    setCopiedShare(kind);
    window.setTimeout(() => setCopiedShare(null), 1600);
  };

  const handleExportRace = async () => {
    setExportingRace(true);
    try {
      await exportRacePng(payload);
    } finally {
      setExportingRace(false);
    }
  };

  return (
    <main className="pulse-app" data-testid="app-loaded">
      <HeroSummary payload={payload} snapshot={snapshot} sourceIsStale={sourceIsStale} />

      <TodayRaceSummary payload={payload} snapshot={snapshot} />

      <section className="race-grid" aria-label="IPL playoff race board">
        <div className="ladder-panel" id="standings" data-testid="standings-ladder">
          <div className="section-heading">
            <div>
              <h2>Standings</h2>
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
              <span className="heading-left">Left</span>
              <span className="heading-top4">Top 4</span>
              <span className="heading-top2">Top 2</span>
            </div>
            {sortedStandings.map((team) => {
              const isTopFour = team.rank <= 4;
              const top4 = payload.analysis.overallProbabilities[team.teamKey]?.top4 ?? 0;
              const top2 = payload.analysis.overallProbabilities[team.teamKey]?.top2 ?? 0;
              return (
                <div className="team-row-block" key={team.teamKey}>
                  <button
                    className={`standing-row ${isTopFour ? 'is-playoff-zone' : ''} ${selectedTeam.teamKey === team.teamKey ? 'is-selected' : ''}`}
                    onClick={() => handleTeamSelect(team)}
                    type="button"
                  >
                    <span className="rank-pill">{team.rank}</span>
                    <span className="team-stripe" style={{ backgroundColor: teamColor(team.teamKey) }} />
                    <span className="team-name">
                      <strong>{team.shortName}</strong>
                      <small>{team.fullName}</small>
                    </span>
                    <span className="team-record">{team.wins}W-{team.losses}L-{team.noResult}NR</span>
                    <span className="team-points">{team.points} pts</span>
                    <span className={`team-nrr ${team.nrr >= 0 ? 'positive' : 'negative'}`}>{formatNrr(team.nrr)}</span>
                    <span className="remaining">{team.remainingMatches} left</span>
                    <span className="prob-mini top4-prob">{formatPercent(top4)}</span>
                    <span className="prob-mini top2-prob">{formatPercent(top2)}</span>
                  </button>
                </div>
              );
            })}
          </div>
        </div>

        <div className="probability-panel" id="top4" data-testid="probability-panel">
          <div className="section-heading">
            <div>
              <span className="panel-kicker">Exact path lab</span>
              <h2>Top 4 Odds</h2>
            </div>
            <div className="export-actions">
              <button onClick={handleCopyCaption} type="button">
                {copiedCaption ? <Check size={13} aria-hidden="true" /> : <Clipboard size={13} aria-hidden="true" />}
                {copiedCaption ? 'Copied' : 'Caption'}
              </button>
              <button disabled={exportingRace} onClick={handleExportRace} type="button">
                <Download size={13} aria-hidden="true" />
                {exportingRace ? 'Making' : 'PNG'}
              </button>
            </div>
          </div>

          <div className="race-bars">
            {sortedStandings.map((team) => {
              const probability = payload.analysis.overallProbabilities[team.teamKey]?.top4 ?? 0;
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

        </div>
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
          <div className="goal-tabs" role="group" aria-label="Select goal">
            {(['4', '2'] as TargetGoal[]).map((goal) => (
              <button
                className={targetGoal === goal ? 'active' : ''}
                key={goal}
                onClick={() => setTargetGoal(goal)}
                type="button"
              >
                {targetLabel(goal)}
              </button>
            ))}
          </div>
        </div>

        <TeamDeepDive
          path={selectedGoalPath}
          payload={payload}
          selectedTop2Path={selectedTop2Path}
          selectedTop4Path={selectedTop4Path}
          target={targetGoal}
          team={selectedTeam}
          topFourProbability={topFourProbability}
          topTwoProbability={topTwoProbability}
        />
      </section>

      <section className="reels-panel" id="reels" aria-labelledby="reels-title">
        <div className="section-heading reels-heading">
          <div>
            <span className="panel-kicker">Share pack</span>
            <h2 id="reels-title">Reels Pack</h2>
          </div>
          <a className="latest-pack-link" href={latestPackHref}>
            Latest pack
            <ExternalLink size={12} aria-hidden="true" />
          </a>
        </div>

        <ReelsPack
          copiedShare={copiedShare}
          error={reelsError}
          manifest={reelsManifest}
          onCopyShare={handleCopyShare}
          payload={payload}
        />
      </section>

      <footer className="pulse-footer">
        <span>
          Updated {formatGeneratedAt(payload.metadata.generated_at)} · {payload.analysis.method} ·{' '}
          {payload.analysis.simulationCount.toLocaleString()} scenarios
        </span>
        <span>NRR is used for standings tiebreaking; scenario math excludes NRR swings.</span>
        <a href={payload.metadata.source_url} target="_blank" rel="noreferrer">
          Source: {payload.metadata.source}
          <ExternalLink size={12} aria-hidden="true" />
        </a>
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
  snapshot,
  sourceIsStale,
}: {
  payload: IplSeasonPayload;
  snapshot: ReturnType<typeof raceSnapshot>;
  sourceIsStale: boolean;
}) => (
  <section className="hero-band compact-hero" aria-labelledby="page-title">
    <div className="hero-copy">
      <div className="hero-main">
        <span className="eyebrow">
          <Zap size={14} aria-hidden="true" />
          IPL Playoff Pulse
        </span>
        <h1 id="page-title">IPL Top 4 Qualification Probabilities</h1>
        <p>Updated daily after the night match</p>
        <nav className="quick-links" aria-label="Page sections">
          <a href="#standings">Standings</a>
          <a href="#top4">Top 4</a>
          <a href="#reels">Reels</a>
          <a href="#deep-dive">Deep dive</a>
        </nav>
      </div>

      <div className="hero-facts" aria-label="Race snapshot">
        <div>
          <span>Current Top 4</span>
          <strong>{snapshot.currentTopFour.map((team) => team.shortName).join(', ')}</strong>
        </div>
        <div>
          <span>Cutline team</span>
          <strong>
            {snapshot.cutlineTeam
              ? `${snapshot.cutlineTeam.shortName} ${formatPercent(top4Probability(payload, snapshot.cutlineTeam.teamKey))}`
              : 'Unavailable'}
          </strong>
        </div>
        <div>
          <span>Nearest challenger</span>
          <strong>
            {snapshot.nearestChallenger
              ? `${snapshot.nearestChallenger.shortName} ${formatPercent(top4Probability(payload, snapshot.nearestChallenger.teamKey))}`
              : 'Unavailable'}
          </strong>
        </div>
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

const TodayRaceSummary = ({
  payload,
  snapshot,
}: {
  payload: IplSeasonPayload;
  snapshot: ReturnType<typeof raceSnapshot>;
}) => (
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
        <span>Current Top 4</span>
        <strong>{snapshot.currentTopFour.map((team) => team.shortName).join(', ')}</strong>
      </article>
      <article>
        <span>Cutline team</span>
        <strong>{snapshot.cutlineTeam?.shortName || 'Unavailable'}</strong>
        {snapshot.cutlineTeam && <small>{formatPercent(top4Probability(payload, snapshot.cutlineTeam.teamKey))} Top 4 chance</small>}
      </article>
      <article>
        <span>Biggest Top 4 riser</span>
        <strong>Previous snapshot unavailable</strong>
        <small>Daily delta needs a prior probability payload.</small>
      </article>
      <article>
        <span>Biggest Top 4 faller</span>
        <strong>Previous snapshot unavailable</strong>
        <small>Daily delta needs a prior probability payload.</small>
      </article>
      <article>
        <span>Teams in danger</span>
        <strong>{snapshot.inDanger.map((team) => team.shortName).join(', ') || 'Unavailable'}</strong>
        <small>Lowest Top 4 odds inside the current top four.</small>
      </article>
      <article>
        <span>Teams almost safe</span>
        <strong>{snapshot.almostSafe.map((team) => team.shortName).join(', ') || 'Unavailable'}</strong>
        <small>{snapshot.almostSafeIsFallback ? 'No team is at 90%; showing highest current odds.' : 'At or above 90% Top 4 chance.'}</small>
      </article>
    </div>
  </section>
);

const TeamDeepDive = ({
  path,
  payload,
  selectedTop2Path,
  selectedTop4Path,
  target,
  team,
  topFourProbability,
  topTwoProbability,
}: {
  path: QualificationPathResult | null;
  payload: IplSeasonPayload;
  selectedTop2Path: QualificationPathResult | null;
  selectedTop4Path: QualificationPathResult | null;
  target: TargetGoal;
  team: IplStanding;
  topFourProbability: number;
  topTwoProbability: number;
}) => {
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
          <span className="mini-label">Top 4 chance</span>
          <strong>{formatPercent(topFourProbability)}</strong>
          <small>{pathShort(selectedTop4Path)}</small>
        </article>
        <article>
          <span className="mini-label">Top 2 chance</span>
          <strong>{formatPercent(topTwoProbability)}</strong>
          <small>{pathShort(selectedTop2Path)}</small>
        </article>
        <article>
          <span className="mini-label">Points, rank, NRR</span>
          <strong>#{team.rank} · {team.points} pts · {formatNrr(team.nrr)}</strong>
          <small>{team.matches} played, {team.remainingMatches} left, max {maxPoints(team)} pts</small>
        </article>
        <article>
          <span className="mini-label">What they need</span>
          <strong>{pathSummary(path, target)}</strong>
          <small>{targetLabel(target)} model, excluding NRR simulation.</small>
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
              <li key={`${team.teamKey}-${target}-help-${impact.fixtureId}`}>
                <strong>{impact.preferredLabel}</strong>
                <small>{impact.label} · adds {impact.impact.toFixed(1)} pts to {targetLabel(target)} odds</small>
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
              <li key={`${team.teamKey}-${target}-hurt-${impact.fixtureId}`}>
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
          <strong>{practicalTakeaway(payload, team, selectedTop4Path)}</strong>
        </article>

        <div className="path-details">
          <h4>{team.shortName} {targetLabel(target)} win buckets</h4>
          <div className="bucket-grid">
            {(path?.ownWinBuckets || []).map((bucket) => (
              <div className="bucket-cell" key={`${team.teamKey}-${target}-${bucket.wins}`}>
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

const ReelsPack = ({
  copiedShare,
  error,
  manifest,
  onCopyShare,
  payload,
}: {
  copiedShare: ShareKind | null;
  error: string | null;
  manifest: ReelsManifest | null;
  onCopyShare: (kind: ShareKind) => void;
  payload: IplSeasonPayload;
}) => {
  if (error) {
    return <p className="reels-state" role="status">Latest Reels manifest unavailable: {error}</p>;
  }

  if (!manifest) {
    return <p className="reels-state" role="status">Loading latest Reels pack...</p>;
  }

  return (
    <>
      <div className="reels-toolbar">
        <div>
          <span className="mini-label">Latest folder</span>
          <strong>{manifest.latestDate || 'Unavailable'}</strong>
          <small>Data updated {formatGeneratedAt(payload.metadata.generated_at)}</small>
        </div>
        <div className="caption-actions" aria-label="Copy captions">
          {(['instagram', 'x', 'whatsapp'] as ShareKind[]).map((kind) => (
            <button key={kind} onClick={() => onCopyShare(kind)} type="button">
              {copiedShare === kind ? <Check size={13} aria-hidden="true" /> : <Clipboard size={13} aria-hidden="true" />}
              {kind === 'instagram' ? 'Instagram caption' : kind === 'x' ? 'X short post' : 'WhatsApp share text'}
            </button>
          ))}
        </div>
      </div>

      <div className="reels-gallery" data-testid="reels-gallery">
        {manifest.slides.map((slide, index) => (
          <ReelSlideCard index={index} key={slide.path} slide={slide} />
        ))}
      </div>

      {manifest.slides.length === 0 && <p className="reels-state">No slide PNGs were listed in the latest manifest.</p>}
      {manifest.warnings.length > 0 && (
        <p className="reels-warning">Pack note: {manifest.warnings.join(' ')}</p>
      )}
    </>
  );
};

const ReelSlideCard = ({ index, slide }: { index: number; slide: ReelsSlide }) => {
  const href = publicAssetUrl(slide.path);
  return (
    <article className="reel-slide-card">
      <a href={href} aria-label={`Open Reels slide ${index + 1}`}>
        <img
          alt={`IPL Playoff Pulse Reels slide ${index + 1}`}
          decoding="async"
          height={slide.imageHeight}
          loading="lazy"
          src={href}
          width={slide.imageWidth}
        />
      </a>
      <div>
        <span>Slide {String(index + 1).padStart(2, '0')}</span>
        <a href={href} download={slide.downloadName}>
          <Download size={13} aria-hidden="true" />
          Download
        </a>
      </div>
    </article>
  );
};

export default App;
