import { describe, it, expect, vi } from 'vitest';
import { runSimulation } from './simulationLogic';
import type { StandingsData } from './simulationLogic';

// Mock team_full_names used by the runSimulation function for teamFullName property
// This avoids depending on the actual teamStyles.ts file in these unit tests.
vi.mock('../teamStyles', () => ({
  team_full_names: {
    TeamA: "Team Alpha",
    TeamB: "Team Bravo",
    TeamC: "Team Charlie",
    TeamD: "Team Delta",
  }
}));


describe('runSimulation', () => {
  it('should correctly simulate a basic scenario', () => {
    const initialStandings: StandingsData = {
      TeamA: { Matches: 0, Wins: 0, Points: 0 },
      TeamB: { Matches: 0, Wins: 0, Points: 0 },
      TeamC: { Matches: 0, Wins: 0, Points: 0 },
    };
    // In resultsDf, the value is the outcome string directly, not an object { Outcome: "..." }
    // This was a slight misinterpretation in the example structure provided in the prompt.
    // The runSimulation function expects: resultsDf: { [fixture: string]: string }
    const resultsDf = {
      "TeamA vs TeamB": "TeamA wins",
      "TeamB vs TeamC": "TeamC wins",
    };
    const analyzedTeamKey = 'TeamA';

    const { matchLog, finalStandings } = runSimulation(initialStandings, resultsDf, analyzedTeamKey);

    expect(matchLog).toHaveLength(2);
    expect(matchLog).toContain('TeamA defeats TeamB');
    expect(matchLog).toContain('TeamC defeats TeamB');

    const teamAData = finalStandings.find(t => t.teamKey === 'TeamA');
    const teamBData = finalStandings.find(t => t.teamKey === 'TeamB');
    const teamCData = finalStandings.find(t => t.teamKey === 'TeamC');

    expect(teamAData?.Points).toBe(2);
    expect(teamAData?.Wins).toBe(1);
    expect(teamAData?.Matches).toBe(1);
    expect(teamAData?.teamFullName).toBe("Team Alpha");


    expect(teamCData?.Points).toBe(2);
    expect(teamCData?.Wins).toBe(1);
    expect(teamCData?.Matches).toBe(1);

    expect(teamBData?.Points).toBe(0);
    expect(teamBData?.Wins).toBe(0);
    expect(teamBData?.Matches).toBe(2);
    
    // Based on points, TeamA and TeamC are tied. TeamA is analyzed, so it gets priority.
    // If not for priority, sorting might be alphabetical or based on other non-implemented tie-breakers.
    // With priority for TeamA: TeamA (2pts), TeamC (2pts), TeamB (0pts)
    expect(finalStandings[0].teamKey).toBe('TeamA'); 
    expect(finalStandings[1].teamKey).toBe('TeamC');
    expect(finalStandings[2].teamKey).toBe('TeamB');
  });

  it('should handle "Result doesn\'t matter" outcome by defaulting to Team A winning', () => {
    const initialStandings: StandingsData = {
      TeamA: { Matches: 0, Wins: 0, Points: 0 },
      TeamB: { Matches: 0, Wins: 0, Points: 0 },
    };
    const resultsDf = {
      "TeamA vs TeamB": "Result doesn't matter",
    };
    const analyzedTeamKey = 'TeamB'; // TeamB is analyzed, but TeamA wins by default

    const { matchLog, finalStandings } = runSimulation(initialStandings, resultsDf, analyzedTeamKey);

    expect(matchLog).toHaveLength(2); // "Fixture: Result didn't matter..." and "TeamA defeats TeamB"
    expect(matchLog).toContain("TeamA vs TeamB: Result didn't matter, defaulted to TeamA winning.");
    expect(matchLog).toContain('TeamA defeats TeamB');

    const teamAData = finalStandings.find(t => t.teamKey === 'TeamA');
    expect(teamAData?.Points).toBe(2);
    expect(teamAData?.Wins).toBe(1);
    expect(teamAData?.Matches).toBe(1);

    const teamBData = finalStandings.find(t => t.teamKey === 'TeamB');
    expect(teamBData?.Points).toBe(0);
    expect(teamBData?.Wins).toBe(0);
    expect(teamBData?.Matches).toBe(1);

    expect(finalStandings[0].teamKey).toBe('TeamA');
  });

  it('should correctly apply tie-breaking for the analyzedTeamKey', () => {
    const initialStandings: StandingsData = {
      TeamA: { Matches: 0, Wins: 0, Points: 0 },
      TeamB: { Matches: 0, Wins: 0, Points: 0 },
      TeamC: { Matches: 0, Wins: 0, Points: 0 }, // TeamC will tie with TeamA
    };
    const resultsDf = {
      "TeamA vs TeamB": "TeamA wins", // TeamA: 2 pts, 1 win
      "TeamC vs TeamB": "TeamC wins", // TeamC: 2 pts, 1 win
    };
    const analyzedTeamKey = 'TeamA';

    const { finalStandings } = runSimulation(initialStandings, resultsDf, analyzedTeamKey);

    const teamAData = finalStandings.find(t => t.teamKey === 'TeamA');
    const teamCData = finalStandings.find(t => t.teamKey === 'TeamC');

    expect(teamAData?.Points).toBe(2);
    expect(teamAData?.Wins).toBe(1);
    expect(teamCData?.Points).toBe(2);
    expect(teamCData?.Wins).toBe(1);

    // TeamA is analyzedTeamKey, so it should be ranked higher than TeamC due to priority
    expect(teamAData?.pos).toBe(1);
    expect(teamCData?.pos).toBe(2);
    expect(finalStandings[0].teamKey).toBe('TeamA');
    expect(finalStandings[1].teamKey).toBe('TeamC');
  });
  
  it('should handle another tie-breaking scenario where analyzedTeamKey is different', () => {
    const initialStandings: StandingsData = {
      TeamA: { Matches: 0, Wins: 0, Points: 0 },
      TeamB: { Matches: 0, Wins: 0, Points: 0 },
      TeamC: { Matches: 0, Wins: 0, Points: 0 }, 
    };
    const resultsDf = {
      "TeamA vs TeamB": "TeamA wins", 
      "TeamC vs TeamB": "TeamC wins", 
    };
    const analyzedTeamKey = 'TeamC'; // This time TeamC is analyzed

    const { finalStandings } = runSimulation(initialStandings, resultsDf, analyzedTeamKey);

    const teamAData = finalStandings.find(t => t.teamKey === 'TeamA');
    const teamCData = finalStandings.find(t => t.teamKey === 'TeamC');

    expect(teamCData?.pos).toBe(1); // TeamC gets priority
    expect(teamAData?.pos).toBe(2);
    expect(finalStandings[0].teamKey).toBe('TeamC');
    expect(finalStandings[1].teamKey).toBe('TeamA');
  });


  it('should handle no fixtures, returning sorted initial standings', () => {
    const initialStandings: StandingsData = {
      TeamA: { Matches: 5, Wins: 2, Points: 4 },
      TeamB: { Matches: 5, Wins: 3, Points: 6 }, // Higher points
      TeamC: { Matches: 5, Wins: 1, Points: 2 },
    };
    const resultsDf = {}; // No fixtures
    const analyzedTeamKey = 'TeamA';

    const { matchLog, finalStandings } = runSimulation(initialStandings, resultsDf, analyzedTeamKey);

    expect(matchLog).toHaveLength(0);
    expect(finalStandings).toHaveLength(3);

    // Check if positions are assigned correctly based on initial points
    expect(finalStandings[0].teamKey).toBe('TeamB'); // 6 points
    expect(finalStandings[0].pos).toBe(1);
    expect(finalStandings[0].teamFullName).toBe("Team Bravo");


    expect(finalStandings[1].teamKey).toBe('TeamA'); // 4 points
    expect(finalStandings[1].pos).toBe(2);

    expect(finalStandings[2].teamKey).toBe('TeamC'); // 2 points
    expect(finalStandings[2].pos).toBe(3);

    // Check that other stats are unchanged
    expect(finalStandings[1].Points).toBe(4);
    expect(finalStandings[1].Wins).toBe(2);
    expect(finalStandings[1].Matches).toBe(5);
  });

  it('should handle a team from resultsDf not being in initialStandings (gracefully)', () => {
    const initialStandings: StandingsData = {
      TeamA: { Matches: 0, Wins: 0, Points: 0 },
      // TeamB is missing from initial standings
    };
    const resultsDf = {
      "TeamA vs TeamB": "TeamB wins", // TeamB is not in initialStandings
    };
    const analyzedTeamKey = 'TeamA';

    const { matchLog, finalStandings } = runSimulation(initialStandings, resultsDf, analyzedTeamKey);
    
    // The simulation logic defaults to teamA (first team in fixture string) if a declared winner is not in standings.
    // And logs a warning.
    expect(matchLog).toContain('Warning: Team TeamB from fixture outcome not in standings. Defaulting winner.');
    // Since TeamB (winner) was not in standings, it defaulted to TeamA winning
    expect(matchLog).toContain('TeamA defeats TeamB');


    const teamAData = finalStandings.find(t => t.teamKey === 'TeamA');
    expect(teamAData?.Points).toBe(2); // TeamA gets points as default winner
    expect(teamAData?.Wins).toBe(1);
    expect(teamAData?.Matches).toBe(1);

    // TeamB should not be in finalStandings as it wasn't in initialStandings
    const teamBData = finalStandings.find(t => t.teamKey === 'TeamB');
    expect(teamBData).toBeUndefined();
  });
});
