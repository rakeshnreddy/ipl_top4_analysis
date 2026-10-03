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

export function top4Probability(payload: IplSeasonPayload, teamKey: string) {
  return payload.analysis.overallProbabilities[teamKey]?.top4 ?? 0;
}

export function top2Probability(payload: IplSeasonPayload, teamKey: string) {
  return payload.analysis.overallProbabilities[teamKey]?.top2 ?? 0;
}

export function raceSnapshot(payload: IplSeasonPayload) {
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
