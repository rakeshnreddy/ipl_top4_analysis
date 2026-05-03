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
import { team_styles } from './teamStyles';

type TargetGoal = '4' | '2';

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
  const [selectedTeamKey, setSelectedTeamKey] = useState<string>('');
  const [targetGoal, setTargetGoal] = useState<TargetGoal>('4');
  const [copiedCaption, setCopiedCaption] = useState(false);
  const [exportingRace, setExportingRace] = useState(false);
  const [error, setError] = useState<string | null>(null);
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
        setSelectedTeamKey(sorted[0]?.teamKey || '');
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

  const sortedStandings = useMemo(() => [...(payload?.standings || [])].sort(rankingSort), [payload]);
  const selectedTeam = useMemo(
    () => sortedStandings.find((team) => team.teamKey === selectedTeamKey) || sortedStandings[0],
    [selectedTeamKey, sortedStandings],
  );
  const nextFixture = payload?.fixtures[0] || null;

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

  const topFourProbability = payload.analysis.overallProbabilities[selectedTeam.teamKey]?.top4 ?? 0;
  const topTwoProbability = payload.analysis.overallProbabilities[selectedTeam.teamKey]?.top2 ?? 0;
  const selectedTop4Path = getPath(payload, selectedTeam.teamKey, '4');
  const selectedTop2Path = getPath(payload, selectedTeam.teamKey, '2');
  const selectedGoalPath = getPath(payload, selectedTeam.teamKey, targetGoal);
  const sourceWarning = payload.metadata.data_freshness_status !== 'fresh' || payload.metadata.warnings.length > 0;
  const handleCopyCaption = async () => {
    const caption = raceCaption(payload);
    try {
      await navigator.clipboard.writeText(caption);
    } catch {
      const element = document.createElement('textarea');
      element.value = caption;
      document.body.appendChild(element);
      element.select();
      document.execCommand('copy');
      document.body.removeChild(element);
    }
    setCopiedCaption(true);
    window.setTimeout(() => setCopiedCaption(false), 1600);
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
      <section className="hero-band compact-hero" aria-labelledby="page-title">
        <div className="hero-copy">
          <div>
            <span className="eyebrow">
              <Zap size={14} aria-hidden="true" />
              IPL 2026 race board
            </span>
            <h1 id="page-title">IPL Playoff Pulse</h1>
          </div>
        </div>
      </section>

      <section className="race-grid" aria-label="IPL playoff race summary">
        <div className="ladder-panel" data-testid="standings-ladder">
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
                    onClick={() => setSelectedTeamKey(team.teamKey)}
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

        <div className="probability-panel" data-testid="probability-panel">
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
                  onClick={() => {
                    setSelectedTeamKey(team.teamKey);
                  }}
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

      <section className="team-detail-panel spotlight-card" aria-label="Selected team detail">
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

        <dl>
          <div>
            <dt>Top 4</dt>
            <dd>{formatPercent(topFourProbability)}</dd>
          </div>
          <div>
            <dt>Top 2</dt>
            <dd>{formatPercent(topTwoProbability)}</dd>
          </div>
          <div>
            <dt>Ceiling</dt>
            <dd>{maxPoints(selectedTeam)} pts</dd>
          </div>
          <div>
            <dt>Path</dt>
            <dd>{pathSummary(targetGoal === '4' ? selectedTop4Path : selectedTop2Path, targetGoal)}</dd>
          </div>
        </dl>

        <TeamDeepDive
          payload={payload}
          selectedTop2Path={selectedTop2Path}
          selectedTop4Path={selectedTop4Path}
          team={selectedTeam}
        />

        <div className="detail-content-grid">
          <div>
            {nextFixture && <NextUpNote fixture={nextFixture} payload={payload} />}
            <SelectedTeamContext
              impacts={sortedImpacts(selectedGoalPath, 5)}
              payload={payload}
              target={targetGoal}
              team={selectedTeam}
            />
          </div>
          <TeamPathDetails
            path={selectedGoalPath}
            target={targetGoal}
            team={selectedTeam}
          />
        </div>
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
            Data note: {payload.metadata.warnings.join(' ')}
          </span>
        )}
      </footer>
    </main>
  );
}

const SelectedTeamContext = ({
  impacts,
  payload,
  target,
  team,
}: {
  impacts: FixtureImpact[];
  payload: IplSeasonPayload;
  target: TargetGoal;
  team: IplStanding;
}) => {
  const ownFixtures = payload.fixtures
    .filter((fixture) => fixture.teamA === team.teamKey || fixture.teamB === team.teamKey)
    .slice(0, 5);
  const neutralImpacts = impacts.filter((impact) => impact.teamA !== team.teamKey && impact.teamB !== team.teamKey).slice(0, 5);

  return (
    <div className="selected-team-context">
      <div className="context-columns">
        <div>
          <h4>Own wins to control</h4>
          <ul className="fixture-list">
            {ownFixtures.map((fixture) => {
              const opponentKey = fixture.teamA === team.teamKey ? fixture.teamB : fixture.teamA;
              return (
                <li key={fixture.id}>
                  <span>{team.shortName} beat {teamShortName(payload, opponentKey)}</span>
                  <small>{formatFixtureTime(fixture)}</small>
                </li>
              );
            })}
          </ul>
        </div>
        <div>
          <h4>{neutralImpacts.length > 0 ? 'Helpful neutral results' : 'Highest swing results'}</h4>
          <ul className="impact-list compact-impact-list">
            {neutralImpacts.length > 0 ? (
              neutralImpacts.map((impact) => (
                <li key={`${team.teamKey}-${target}-${impact.fixtureId}`}>
                  <strong>{impact.preferredLabel}</strong>
                  <small>{impact.label} · adds {impact.impact.toFixed(1)} pts to {targetLabel(target)} odds</small>
                </li>
              ))
            ) : (
              impacts.slice(0, 3).map((impact) => (
                <li key={`${team.teamKey}-${target}-${impact.fixtureId}`}>
                  <strong>{impact.preferredLabel}</strong>
                  <small>{impact.label} · adds {impact.impact.toFixed(1)} pts to {targetLabel(target)} odds</small>
                </li>
              ))
            )}
            {impacts.length === 0 && (
              <li>
                <span>No material fixture dependency found.</span>
                <strong>Either result</strong>
                <small>0.0 point swing</small>
              </li>
            )}
          </ul>
        </div>
      </div>
    </div>
  );
};

const TeamDeepDive = ({
  payload,
  selectedTop2Path,
  selectedTop4Path,
  team,
}: {
  payload: IplSeasonPayload;
  selectedTop2Path: QualificationPathResult | null;
  selectedTop4Path: QualificationPathResult | null;
  team: IplStanding;
}) => {
  const top4 = payload.analysis.overallProbabilities[team.teamKey]?.top4 ?? 0;
  const top2 = payload.analysis.overallProbabilities[team.teamKey]?.top2 ?? 0;

  return (
    <div className="deep-dive-grid">
      <article>
        <span className="mini-label">Table position</span>
        <strong>#{team.rank} · {team.points} pts · {formatNrr(team.nrr)} NRR</strong>
        <small>{team.matches} played, {team.remainingMatches} left, max {maxPoints(team)} pts</small>
      </article>
      <article>
        <span className="mini-label">Top 4 outlook</span>
        <strong>{formatPercent(top4)}</strong>
        <small>{pathShort(selectedTop4Path)}</small>
      </article>
      <article>
        <span className="mini-label">Top 2 outlook</span>
        <strong>{formatPercent(top2)}</strong>
        <small>{pathShort(selectedTop2Path)}</small>
      </article>
      <article>
        <span className="mini-label">Practical brief</span>
        <strong>{team.shortName} need own wins first.</strong>
        <small>Neutral help matters most where the swing list calls out direct playoff rivals dropping points.</small>
      </article>
    </div>
  );
};

const TeamPathDetails = ({
  path,
  target,
  team,
}: {
  path: QualificationPathResult | null;
  target: TargetGoal;
  team: IplStanding;
}) => (
  <div className="path-details">
    <h4>{team.shortName} {targetLabel(target)} Win Buckets</h4>
    <div className="bucket-grid">
      {(path?.ownWinBuckets || []).map((bucket) => (
        <div className="bucket-cell" key={`${team.teamKey}-${target}-${bucket.wins}`}>
          <span>{bucket.wins}W</span>
          <strong>{formatPercent(bucket.probability)}</strong>
          <small>{bucket.scenarios.toLocaleString()} scenarios</small>
        </div>
      ))}
    </div>
  </div>
);

const NextUpNote = ({ fixture, payload }: { fixture: IplFixture; payload: IplSeasonPayload }) => {
  const left = payload.standings.find((team) => team.teamKey === fixture.teamA);
  const right = payload.standings.find((team) => team.teamKey === fixture.teamB);

  return (
    <aside className="next-up-note" aria-label="Next fixture">
      <CalendarClock size={16} aria-hidden="true" />
      <div>
        <span className="mini-label">Next fixture</span>
        <strong>{left?.shortName || fixture.teamA} vs {right?.shortName || fixture.teamB}</strong>
        <small>{formatFixtureTime(fixture)} · {fixture.venue || 'Venue TBA'}</small>
      </div>
    </aside>
  );
};

export default App;
