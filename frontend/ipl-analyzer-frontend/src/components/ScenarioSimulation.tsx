import React, { useEffect, useState } from 'react';

import { team_full_names, team_styles } from '../teamStyles'; import type { TeamNames, TeamStyle } from '../teamStyles';

// Copied from CurrentStandings.tsx
interface TeamStats {
  Matches: number;
  Wins: number;
  Points: number;
}

// Copied from CurrentStandings.tsx
interface StandingsData {
  [key: string]: TeamStats;
}

// Types specific to this component's data fetching needs, not directly used by runSimulation
interface FetchedStandingsData {
  standings: StandingsData;
}

interface TeamAnalysisResult {
  percentage: number;
  results_df: { [fixture: string]: { Outcome: string; [key: string]: any } }; // Updated type
}

interface TeamAnalysisData {
  [target: string]: {
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
  resultsDf: { [fixture: string]: { Outcome: string; [key: string]: any } }, // Updated parameter type
  analyzedTeamKey: string
): { matchLog: string[]; finalStandings: SimulatedTeamStats[] } => {
  const currentStandings = JSON.parse(JSON.stringify(initialStandings)); // Deep copy
  const matchLog: string[] = [];

  for (const fixture in resultsDf) {
    const teams = fixture.split(" vs ");
    if (teams.length !== 2) {
      matchLog.push(`Invalid fixture string: ${fixture}`);
      continue;
    }
    const teamA = teams[0];
    const teamB = teams[1];

    let winner: string;
    let loser: string;

    const outcomeObject = resultsDf[fixture]; // outcomeObject is now an object
    const outcomeString = outcomeObject.Outcome; // Extract Outcome property
    if (outcomeString.includes("wins")) {
      winner = outcomeString.replace(" wins", "");
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
  const [initialStandings, setInitialStandings] = useState<StandingsData | null>(null); // Type from simulationLogic
  const [analysisData, setAnalysisData] = useState<TeamAnalysisData | null>(null);
  const [availableTeams, setAvailableTeams] = useState<TeamNames>({});
  const [selectedTeamKey, setSelectedTeamKey] = useState<string>('');
  const [selectedTarget, setSelectedTarget] = useState<'4' | '2'>('4');
  const [simulatedMatchLog, setSimulatedMatchLog] = useState<string[]>([]);
  const [simulatedFinalStandings, setSimulatedFinalStandings] = useState<SimulatedTeamStats[]>([]);
  const [simulationRun, setSimulationRun] = useState<boolean>(false);
  const [loading, setLoading] = useState<boolean>(true);
  const [simulatingInProgress, setSimulatingInProgress] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [simulationMessage, setSimulationMessage] = useState<string>('');

  useEffect(() => {
    setLoading(true);
    Promise.all([
      fetch(`${import.meta.env.BASE_URL}current_standings.json`).then(res => res.ok ? res.json() : Promise.reject(new Error(`Standings fetch error: ${res.status}`))),
      fetch(`${import.meta.env.BASE_URL}analysis_results.json`).then(res => res.ok ? res.json() : Promise.reject(new Error(`Analysis fetch error: ${res.status}`)))
    ])
    .then(([standingsResult, analysisResult]: [FetchedStandingsData, FetchedAnalysisData]) => {
      if (!standingsResult.standings) {
        throw new Error("Standings data is missing in the response.");
      }
      setInitialStandings(standingsResult.standings);
      
      if (!analysisResult.analysis_data || !analysisResult.analysis_data.team_analysis) {
        throw new Error("Team analysis data is missing or malformed in the response.");
      }
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

      if (teamsInAnalysis.length > 0 && !selectedTeamKey) {
        setSelectedTeamKey(teamsInAnalysis[0]);
      }
      setError(null);
    })
    .catch(fetchError => {
      console.error("Failed to load data for simulation:", fetchError);
      setError(`Failed to load essential data. ${fetchError.message}`);
    })
    .finally(() => {
      setLoading(false);
    });
  }, [selectedTeamKey]);

  const handleSimulate = () => {
    setSimulationRun(false);
    setSimulationMessage('');
    setSimulatingInProgress(true);

    if (!initialStandings || !analysisData || !selectedTeamKey) {
      setSimulationMessage("Error: Data not loaded or team not selected.");
      setSimulatingInProgress(false);
      return;
    }

    const teamAnalysisForTarget = analysisData[selectedTarget];
    if (!teamAnalysisForTarget || !teamAnalysisForTarget[selectedTeamKey]) {
      setSimulationMessage(`Error: No analysis data found for ${team_full_names[selectedTeamKey]} and Top ${selectedTarget}.`);
      setSimulatingInProgress(false);
      return;
    }

    const { results_df, percentage } = teamAnalysisForTarget[selectedTeamKey];

    if (Object.keys(results_df).length === 0 && percentage === 0) {
      setSimulationMessage(`${team_full_names[selectedTeamKey]} has a 0% chance to qualify for Top ${selectedTarget}. Scenario cannot be meaningfully simulated based on required wins.`);
      setSimulatedMatchLog([]);
      setSimulatedFinalStandings([]);
      setSimulationRun(true);
      setSimulatingInProgress(false);
      return;
    }
    if (Object.keys(results_df).length === 0 && percentage === 100) {
      setSimulationMessage(`${team_full_names[selectedTeamKey]} has a 100% chance to qualify. Simulation based on specific required match outcomes may not be applicable as the team likely already qualifies or qualification doesn't hinge on these specific games.`);
      const { finalStandings } = runSimulation(initialStandings, {}, selectedTeamKey);
      setSimulatedMatchLog(["Team already qualifies or qualification does not depend on specific remaining matches."]);
      setSimulatedFinalStandings(finalStandings);
      setSimulationRun(true);
      setSimulatingInProgress(false);
      return;
    }

    const { matchLog, finalStandings } = runSimulation(initialStandings, results_df, selectedTeamKey);
    setSimulatedMatchLog(matchLog);
    setSimulatedFinalStandings(finalStandings);
    setSimulationRun(true);
    setSimulatingInProgress(false);
  };

  if (loading) return <p role="status" aria-live="polite">Loading simulation data...</p>;
  if (error) return <p role="alert" aria-live="assertive" style={{ color: 'red' }}>{error}</p>;

  return (
    <div>
      <div className="simulation-controls">
        <div className="control-group">
          <label htmlFor="team-select-sim">Select Team: </label>
          <select id="team-select-sim" value={selectedTeamKey} onChange={e => setSelectedTeamKey(e.target.value)} disabled={simulatingInProgress || Object.keys(availableTeams).length === 0} aria-controls="simulation-results">
            <option value="">--Select a Team--</option>
            {Object.entries(availableTeams).map(([key, name]) => (
              <option key={key} value={key}>{name}</option>
            ))}
          </select>
        </div>
        <fieldset className="control-group">
          <legend>Select Target:</legend>
          <label htmlFor="top4-radio-sim">
            <input type="radio" id="top4-radio-sim" name="target-sim" value="4" checked={selectedTarget === '4'} onChange={e => setSelectedTarget(e.target.value as '4' | '2')} disabled={simulatingInProgress} aria-controls="simulation-results"/> Top 4
          </label>
          <label htmlFor="top2-radio-sim">
            <input type="radio" id="top2-radio-sim" name="target-sim" value="2" checked={selectedTarget === '2'} onChange={e => setSelectedTarget(e.target.value as '4' | '2')} disabled={simulatingInProgress} aria-controls="simulation-results"/> Top 2
          </label>
        </fieldset>
        <button onClick={handleSimulate} disabled={loading || !selectedTeamKey || simulatingInProgress} className="button success">
          {simulatingInProgress ? 'Simulating...' : 'Simulate Scenario'}
        </button>
      </div>

      {simulatingInProgress && <p role="status" aria-live="polite">Processing simulation, please wait...</p>}
      {simulationMessage && !simulatingInProgress && (
        <p className="simulation-message" role="status">{simulationMessage}</p>
      )}

      {simulationRun && !simulatingInProgress && (
        <div id="simulation-results" className="simulation-results-container mt-2">
          <div className="match-log-container">
            <h4>Match Results Log:</h4>
            <textarea value={simulatedMatchLog.join('\n')} readOnly rows={10} aria-label="Simulated match results log" />
          </div>
          <div className="final-standings-container">
            <h4>Final Standings (Simulated):</h4>
            {simulatedFinalStandings.length > 0 ? (
              <div className="table-responsive">
                <table>
                  <caption>Simulated final standings for the selected scenario.</caption>
                  <thead>
                    <tr>
                      <th scope="col">Pos</th>
                      <th scope="col">Team</th>
                      <th scope="col">Matches</th>
                      <th scope="col">Wins</th>
                      <th scope="col">Points</th>
                    </tr>
                  </thead>
                  <tbody>
                    {simulatedFinalStandings.map((team) => {
                      const teamStyle = team_styles[team.teamKey] as TeamStyle | undefined;
                      return (
                        <tr key={team.teamKey} style={{ backgroundColor: teamStyle?.bg || '#FFFFFF', color: teamStyle?.text || '#000000' }}>
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
              </div>
            ) : (
              <p>No final standings to display for this simulation.</p>
            )}
          </div>
        </div>
      )}
       {!selectedTeamKey && !loading && Object.keys(availableTeams).length > 0 && (
        <p className="mt-2">Please select a team to simulate a scenario.</p>
      )}
    </div>
  );
};

export default ScenarioSimulation;
