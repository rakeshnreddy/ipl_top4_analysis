import React, { useEffect, useState } from 'react';
import { team_full_names, team_styles, TeamNames, TeamStyle } from '../teamStyles';

// Types from previous components (can be moved to a common types.ts later)
interface TeamStats {
  Matches: number;
  Wins: number;
  Points: number;
}

interface StandingsData {
  [key: string]: TeamStats;
}

interface FetchedStandingsData {
  standings: StandingsData;
  // last_updated, source also present but not directly used in simulation logic here
}

interface TeamAnalysisResult {
  percentage: number;
  results_df: { [fixture: string]: string }; // fixture: "TeamA vs TeamB", outcome: "TeamA wins"
}

interface TeamAnalysisData {
  [target: string]: { // "2" or "4"
    [teamKey: string]: TeamAnalysisResult;
  };
}

interface AnalysisMetadata {
  method_used: string;
  timestamp: string;
}

interface FetchedAnalysisData {
  metadata: AnalysisMetadata;
  analysis_data: {
    team_analysis: TeamAnalysisData;
  };
}

interface SimulatedTeamStats extends TeamStats {
  teamKey: string;
  teamFullName: string;
  pos: number;
  priority?: number; // For tie-breaking
}

// Helper function for simulation
const runSimulation = (
  initialStandings: StandingsData,
  resultsDf: { [fixture: string]: string },
  analyzedTeamKey: string
): { matchLog: string[]; finalStandings: SimulatedTeamStats[] } => {
  const currentStandings = JSON.parse(JSON.stringify(initialStandings)); // Deep copy
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
      loser = winner === teamA ? teamB : teamA;
    } else { // "Result doesn't matter" or other unexpected
      // Defaulting to Team A for "Result doesn't matter"
      winner = teamA;
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
    priority: teamKey === analyzedTeamKey ? 0 : 1, // Lower number = higher priority
  }));

  // Sort: Points (desc), Priority (asc), Wins (desc)
  finalStandingsArray.sort((a, b) => {
    if (b.Points !== a.Points) {
      return b.Points - a.Points;
    }
    if (a.priority !== b.priority) {
      return a.priority - b.priority;
    }
    return b.Wins - a.Wins;
  });

  const finalProcessedStandings: SimulatedTeamStats[] = finalStandingsArray.map((team, index) => ({
    ...team,
    teamFullName: team_full_names[team.teamKey] || team.teamKey,
    pos: index + 1,
  }));

  return { matchLog, finalStandings: finalProcessedStandings };
};


const ScenarioSimulation: React.FC = () => {
  const [initialStandings, setInitialStandings] = useState<StandingsData | null>(null);
  const [analysisData, setAnalysisData] = useState<TeamAnalysisData | null>(null);
  const [availableTeams, setAvailableTeams] = useState<TeamNames>({});
  const [selectedTeamKey, setSelectedTeamKey] = useState<string>('');
  const [selectedTarget, setSelectedTarget] = useState<'4' | '2'>('4');

  const [simulatedMatchLog, setSimulatedMatchLog] = useState<string[]>([]);
  const [simulatedFinalStandings, setSimulatedFinalStandings] = useState<SimulatedTeamStats[]>([]);
  const [simulationRun, setSimulationRun] = useState<boolean>(false);

  const [loading, setLoading] = useState<boolean>(true); // For initial data load
  const [simulatingInProgress, setSimulatingInProgress] = useState<boolean>(false); // For simulation process
  const [error, setError] = useState<string | null>(null);
  const [simulationMessage, setSimulationMessage] = useState<string>('');


  useEffect(() => {
    Promise.all([
      fetch('/current_standings.json').then(res => res.ok ? res.json() : Promise.reject(`Standings fetch error: ${res.status}`)),
      fetch('/analysis_results.json').then(res => res.ok ? res.json() : Promise.reject(`Analysis fetch error: ${res.status}`))
    ])
    .then(([standingsResult, analysisResult]: [FetchedStandingsData, FetchedAnalysisData]) => {
      setInitialStandings(standingsResult.standings);
      const teamAnalysis = analysisResult.analysis_data.team_analysis;
      setAnalysisData(teamAnalysis);

      const teamsInAnalysis = teamAnalysis['4'] ? Object.keys(teamAnalysis['4']) : [];
      const validTeams: TeamNames = {};
      teamsInAnalysis.forEach(key => {
        if (team_full_names[key]) {
          validTeams[key] = team_full_names[key];
        }
      });
      setAvailableTeams(validTeams);

      if (teamsInAnalysis.length > 0) {
        setSelectedTeamKey(teamsInAnalysis[0]);
      }
      setLoading(false);
    })
    .catch(fetchError => {
      console.error("Failed to load data for simulation:", fetchError);
      setError(`Failed to load data. ${fetchError.toString()}`);
      setLoading(false);
    });
  }, []);

  const handleSimulate = () => {
    setSimulationRun(false);
    setSimulationMessage('');
    setSimulatingInProgress(true); // Start simulation loading

    if (!initialStandings || !analysisData || !selectedTeamKey) {
      setSimulationMessage("Error: Data not loaded or team not selected.");
      setSimulatingInProgress(false); // End simulation loading
      return;
    }

    const teamAnalysisForTarget = analysisData[selectedTarget];
    if (!teamAnalysisForTarget || !teamAnalysisForTarget[selectedTeamKey]) {
      setSimulationMessage(`Error: No analysis data found for ${team_full_names[selectedTeamKey]} and Top ${selectedTarget}.`);
      setSimulatingInProgress(false); // End simulation loading
      return;
    }

    const resultsDf = teamAnalysisForTarget[selectedTeamKey].results_df;
    const percentage = teamAnalysisForTarget[selectedTeamKey].percentage;

    if (Object.keys(resultsDf).length === 0 && percentage === 0) {
        setSimulationMessage(`${team_full_names[selectedTeamKey]} has a 0% chance to qualify for Top ${selectedTarget}. Scenario cannot be meaningfully simulated based on required wins.`);
        setSimulatedMatchLog([]);
        setSimulatedFinalStandings([]);
        setSimulationRun(true); // Indicate simulation "attempted"
        setSimulatingInProgress(false); // End simulation loading
        return;
    }
     if (Object.keys(resultsDf).length === 0 && percentage === 100) {
        setSimulationMessage(`${team_full_names[selectedTeamKey]} has a 100% chance to qualify for Top ${selectedTarget}. Simulation based on specific required match outcomes may not be applicable.`);
        // Optionally, you could simulate a "no change" or random scenario if desired
        // For now, just show message and don't run detailed fixture simulation.
        setSimulatedMatchLog(["Team already qualifies / No specific fixtures to force."]);
        // Display initial standings as "final" or calculate them after remaining matches (if any) are played randomly
        // This part might need more sophisticated handling if a 100% scenario is common
        const { finalStandings } = runSimulation(initialStandings, {}, selectedTeamKey); // Empty results DF
        setSimulatedFinalStandings(finalStandings);
        setSimulationRun(true);
        setSimulatingInProgress(false); // End simulation loading
        return;
    }


    const { matchLog, finalStandings } = runSimulation(initialStandings, resultsDf, selectedTeamKey);
    setSimulatedMatchLog(matchLog);
    setSimulatedFinalStandings(finalStandings);
    setSimulationRun(true);
    setSimulatingInProgress(false); // End simulation loading
  };


  if (loading) return <p>Loading simulation data...</p>;
  if (error) return <p style={{ color: 'red' }}>{error}</p>;

  return (
    <div>
      <div className="simulation-controls">
        <div className="control-group">
          <label htmlFor="team-select-sim">Select Team: </label>
          <select id="team-select-sim" value={selectedTeamKey} onChange={e => setSelectedTeamKey(e.target.value)} disabled={simulatingInProgress}>
            {Object.entries(availableTeams).map(([key, name]) => (
              <option key={key} value={key}>{name}</option>
            ))}
          </select>
        </div>
        <div className="control-group">
          <label>Select Target: </label>
          <label htmlFor="top4-radio-sim">
            <input type="radio" id="top4-radio-sim" name="target-sim" value="4" checked={selectedTarget === '4'} onChange={e => setSelectedTarget(e.target.value as '4' | '2')} disabled={simulatingInProgress} /> Top 4
          </label>
          <label htmlFor="top2-radio-sim">
            <input type="radio" id="top2-radio-sim" name="target-sim" value="2" checked={selectedTarget === '2'} onChange={e => setSelectedTarget(e.target.value as '4' | '2')} disabled={simulatingInProgress} /> Top 2
          </label>
        </div>
        <button onClick={handleSimulate} disabled={loading || !selectedTeamKey || simulatingInProgress}>
          {simulatingInProgress ? 'Simulating...' : 'Simulate Scenario'}
        </button>
      </div>

      {simulatingInProgress && <p>Processing simulation, please wait...</p>}
      {simulationMessage && !simulatingInProgress && <p className="simulation-message">{simulationMessage}</p>}

      {simulationRun && !simulatingInProgress && (
        <div className="simulation-results-container">
          <div className="match-log-container">
            <h4>Match Results Log:</h4>
            <textarea value={simulatedMatchLog.join('\n')} readOnly rows={10} />
          </div>
          <div className="final-standings-container">
            <h4>Final Standings:</h4>
            {simulatedFinalStandings.length > 0 ? (
              <table>
                <thead>
                  <tr>
                    <th>Pos</th>
                    <th>Team</th>
                    <th>Matches</th>
                    <th>Wins</th>
                    <th>Points</th>
                  </tr>
                </thead>
                <tbody>
                  {simulatedFinalStandings.map((team) => {
                    const style = team_styles[team.teamKey] as TeamStyle || {};
                    return (
                      <tr key={team.teamKey} style={{ backgroundColor: style.bg, color: style.text }}>
                        <td>{team.pos}</td>
                        <td>{team.teamFullName}</td>
                        <td>{team.Matches}</td>
                        <td>{team.Wins}</td>
                        <td>{team.Points}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            ) : (
              <p>No final standings to display.</p>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default ScenarioSimulation;
