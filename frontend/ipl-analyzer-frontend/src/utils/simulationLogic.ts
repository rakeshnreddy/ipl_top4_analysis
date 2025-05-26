import { team_full_names } from '../teamStyles';

// Type interfaces for simulation logic
export interface TeamStats {
  Matches: number;
  Wins: number;
  Points: number;
}

export interface StandingsData {
  [key: string]: TeamStats;
}

export interface SimulatedTeamStats extends TeamStats {
  teamKey: string;
  teamFullName: string;
  pos: number;
  priority?: number;
}

// runSimulation function, moved from ScenarioSimulation.tsx
export const runSimulation = (
  initialStandings: StandingsData,
  resultsDf: { [fixture: string]: string }, // results_df has string outcomes like "TeamA wins"
  analyzedTeamKey: string
): { matchLog: string[]; finalStandings: SimulatedTeamStats[] } => {
  const currentStandings = JSON.parse(JSON.stringify(initialStandings));
  const matchLog: string[] = [];

  for (const fixture in resultsDf) {
    const outcome = resultsDf[fixture];
    const teams = fixture.split(" vs ");
    if (teams.length !== 2) {
      matchLog.push(`Invalid fixture string: ${fixture}`);
      continue;
    }
    const teamA = teams[0];
    const teamB = teams[1];
    let winner: string;
    let loser: string;

    if (outcome.includes("wins")) {
      winner = outcome.replace(" wins", "");
      if (!currentStandings[winner]) {
        matchLog.push(`Warning: Team ${winner} from fixture outcome not in standings. Defaulting winner.`);
        winner = teamA; 
      }
      loser = winner === teamA ? teamB : teamA;
      if (!currentStandings[loser]) {
        matchLog.push(`Warning: Team ${loser} from fixture outcome not in standings. Defaulting loser.`);
      }
    } else { // "Result doesn't matter" or other unexpected
      winner = teamA; // Default for "Result doesn't matter"
      loser = teamB;
      matchLog.push(`${fixture}: Result didn't matter, defaulted to ${winner} winning.`);
    }
    
    matchLog.push(`${winner} defeats ${loser}`);

    if (currentStandings[winner]) {
      currentStandings[winner].Wins += 1;
      currentStandings[winner].Points += 2;
      currentStandings[winner].Matches += 1;
    }
    if (currentStandings[loser]) {
      currentStandings[loser].Matches += 1;
    }
  }

  const finalStandingsArray = Object.entries(currentStandings).map(([teamKey, stats]) => ({
    teamKey,
    ...(stats as TeamStats),
    priority: teamKey === analyzedTeamKey ? 0 : 1,
  }));

  finalStandingsArray.sort((a, b) => {
    if (b.Points !== a.Points) return b.Points - a.Points;
    if (a.priority !== b.priority) return a.priority - b.priority;
    return b.Wins - a.Wins;
  });

  const finalProcessedStandings: SimulatedTeamStats[] = finalStandingsArray.map((team, index) => ({
    ...team,
    teamFullName: team_full_names[team.teamKey] || team.teamKey,
    pos: index + 1,
  }));

  return { matchLog, finalStandings: finalProcessedStandings };
};
