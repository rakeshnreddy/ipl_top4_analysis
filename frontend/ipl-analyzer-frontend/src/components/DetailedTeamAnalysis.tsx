import React, { useEffect, useState } from 'react';
import { team_full_names, team_short_names, TeamNames } from '../teamStyles';

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
    // overall_probabilities might also be here but not used by this component
  };
}

interface FixtureOutcome {
  fixture: string;
  outcome: string;
}

const DetailedTeamAnalysis: React.FC = () => {
  const [analysisData, setAnalysisData] = useState<TeamAnalysisData | null>(null);
  const [metadata, setMetadata] = useState<AnalysisMetadata | null>(null);
  const [availableTeams, setAvailableTeams] = useState<TeamNames>({});
  const [selectedTeamKey, setSelectedTeamKey] = useState<string>('');
  const [selectedTarget, setSelectedTarget] = useState<'4' | '2'>('4'); // Default to Top 4
  const [teamResults, setTeamResults] = useState<TeamAnalysisResult | null>(null);
  const [fixtureOutcomes, setFixtureOutcomes] = useState<FixtureOutcome[]>([]);

  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch('/analysis_results.json')
      .then((response) => {
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }
        return response.json();
      })
      .then((data: FetchedAnalysisData) => {
        setMetadata(data.metadata);
        const teamAnalysis = data.analysis_data.team_analysis;
        setAnalysisData(teamAnalysis);

        // Determine available teams from the analysis data (for Top 4 initially)
        const teamsInAnalysis = teamAnalysis['4'] ? Object.keys(teamAnalysis['4']) : [];
        const validTeams: TeamNames = {};
        teamsInAnalysis.forEach(key => {
          if (team_full_names[key]) {
            validTeams[key] = team_full_names[key];
          }
        });
        setAvailableTeams(validTeams);

        if (teamsInAnalysis.length > 0) {
          setSelectedTeamKey(teamsInAnalysis[0]); // Select the first available team
        }
        setLoading(false);
      })
      .catch((fetchError) => {
        console.error("Failed to load analysis results:", fetchError);
        setError(`Failed to load analysis data. ${fetchError.message}`);
        setLoading(false);
      });
  }, []);

  useEffect(() => {
    if (analysisData && selectedTeamKey && selectedTarget) {
      const results = analysisData[selectedTarget]?.[selectedTeamKey];
      if (results) {
        setTeamResults(results);
        const outcomes = Object.entries(results.results_df).map(([fixture, outcome]) => ({
          fixture,
          outcome,
        }));
        setFixtureOutcomes(outcomes);
      } else {
        setTeamResults(null);
        setFixtureOutcomes([]);
      }
    }
  }, [analysisData, selectedTeamKey, selectedTarget]);

  const handleTeamChange = (event: React.ChangeEvent<HTMLSelectElement>) => {
    setSelectedTeamKey(event.target.value);
  };

  const handleTargetChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setSelectedTarget(event.target.value as '4' | '2');
  };

  if (loading) {
    return <p>Loading detailed analysis...</p>;
  }

  if (error) {
    return <p style={{ color: 'red' }}>{error}</p>;
  }

  return (
    <div>
      {metadata && (
        <div style={{ marginBottom: '10px', fontSize: '0.9em', color: '#555' }}>
          <p>Analysis Method: {metadata.method_used}</p>
          <p>Last Updated: {new Date(metadata.timestamp).toLocaleString()}</p>
        </div>
      )}

      <div className="analysis-controls">
        <div className="control-group">
          <label htmlFor="team-select">Select Team: </label>
          <select id="team-select" value={selectedTeamKey} onChange={handleTeamChange}>
            {Object.entries(availableTeams).map(([key, name]) => (
              <option key={key} value={key}>{name}</option>
            ))}
          </select>
        </div>

        <div className="control-group">
          <label>Select Target: </label>
          <label htmlFor="top4-radio">
            <input
              type="radio"
              id="top4-radio"
              name="target"
              value="4"
              checked={selectedTarget === '4'}
              onChange={handleTargetChange}
            /> Top 4
          </label>
          <label htmlFor="top2-radio">
            <input
              type="radio"
              id="top2-radio"
              name="target"
              value="2"
              checked={selectedTarget === '2'}
              onChange={handleTargetChange}
            /> Top 2
          </label>
        </div>
      </div>

      {selectedTeamKey && teamResults && (
        <div className="analysis-results">
          <h3>
            {team_full_names[selectedTeamKey] || selectedTeamKey} - Top {selectedTarget} Analysis
          </h3>
          <p>
            <strong>
              Chance to qualify for Top {selectedTarget}: {teamResults.percentage.toFixed(2)}%
            </strong>
          </p>
          <h4>Required / Frequent Outcomes:</h4>
          {fixtureOutcomes.length > 0 ? (
            <table>
              <thead>
                <tr>
                  <th>Fixture</th>
                  <th>Outcome</th>
                </tr>
              </thead>
              <tbody>
                {fixtureOutcomes.map((item, index) => (
                  <tr key={index}>
                    <td>{item.fixture}</td>
                    <td>{item.outcome}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p>No specific outcomes data available for this selection. This might mean the chance is 0% or 100%, or data is missing.</p>
          )}
        </div>
      )}
      {!teamResults && selectedTeamKey && !loading && (
         <p>No analysis data available for {team_full_names[selectedTeamKey] || selectedTeamKey} for Top {selectedTarget}.</p>
      )}
    </div>
  );
};

export default DetailedTeamAnalysis;
