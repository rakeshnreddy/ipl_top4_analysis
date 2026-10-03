import type { IplSeasonPayload, IplStanding, LeagueTeam } from '../data/iplData';
import { team_styles } from '../teamStyles';

export const formatPercent = (value: number) =>
  `${value.toLocaleString(undefined, { maximumFractionDigits: value % 1 === 0 ? 0 : 1 })}%`;

export const hasNrr = (value: number | null | undefined): value is number =>
  typeof value === 'number' && Number.isFinite(value);

export const formatNrr = (value: number | null | undefined) => (hasNrr(value) ? `${value >= 0 ? '+' : ''}${value.toFixed(3)}` : 'N/A');

export const formatGeneratedAt = (value: string) =>
  new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value));

export const formatGeneratedDate = (value: string) =>
  new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
  }).format(new Date(value));

// Colours for the league on screen; a page only ever shows one league.
let palette: Record<string, { color: string; textColor: string }> = {};

export function setTeamPalette(teams: LeagueTeam[] | undefined) {
  palette = Object.fromEntries((teams || []).map((team) => [team.key, { color: team.color, textColor: team.textColor }]));
}

export const teamColor = (teamKey: string) => palette[teamKey]?.color || team_styles[teamKey]?.bg || '#2d405f';
export const teamTextColor = (teamKey: string) =>
  palette[teamKey]?.textColor || team_styles[teamKey]?.text || '#ffffff';

export function rankingSort(a: IplStanding, b: IplStanding) {
  const nrrSort = hasNrr(a.nrr) && hasNrr(b.nrr) ? b.nrr - a.nrr : 0;
  return b.points - a.points || nrrSort || a.rank - b.rank || b.wins - a.wins || a.fullName.localeCompare(b.fullName);
}

/** A team's chance of finishing in the top `size`; payloads store it as `top{size}`. */
export function tierProbability(payload: IplSeasonPayload, teamKey: string, size: number) {
  return payload.analysis.overallProbabilities[teamKey]?.[`top${size}`] ?? 0;
}

/** Who holds the playoff places right now and who is chasing them. */
export function raceSnapshot(payload: IplSeasonPayload, playoffSize = 4) {
  const chance = (team: IplStanding) => tierProbability(payload, team.teamKey, playoffSize);
  const ordered = [...payload.standings].sort(rankingSort);
  const currentTop = ordered.slice(0, playoffSize);
  const cutlineTeam = currentTop[playoffSize - 1] || null;
  const nearestChallenger = [...ordered.slice(playoffSize)].sort((a, b) => chance(b) - chance(a))[0] || null;
  const inDanger = [...currentTop].sort((a, b) => chance(a) - chance(b)).slice(0, 2);
  const almostSafeByThreshold = ordered.filter((team) => chance(team) >= 90);
  const almostSafe = almostSafeByThreshold.length > 0
    ? almostSafeByThreshold
    : [...ordered].sort((a, b) => chance(b) - chance(a)).slice(0, 2);

  return {
    ordered,
    currentTop,
    cutlineTeam,
    nearestChallenger,
    inDanger,
    almostSafe,
    almostSafeIsFallback: almostSafeByThreshold.length === 0,
  };
}
