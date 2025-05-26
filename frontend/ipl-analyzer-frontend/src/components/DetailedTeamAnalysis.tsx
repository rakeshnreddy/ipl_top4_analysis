import React, { useEffect, useState } from 'react';
import { team_full_names, TeamNames } from '../teamStyles';

interface TeamAnalysisResult {
  percentage: number;
  results_df: { [fixture: string]: string };
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

interface FixtureOutcome {
  fixture: string;
  outcome: string;
}

const DetailedTeamAnalysis: React.FC = () => {
  const [analysisData, setAnalysisData] = useState<TeamAnalysisData | null>(null);
  const [metadata, setMetadata] = useState<AnalysisMetadata | null>(null);
  const [availableTeams, setAvailableTeams] = useState<TeamNames>({});
  const [selectedTeamKey, setSelectedTeamKey] = useState<string>('');
  const [selectedTarget, setSelectedTarget] = useState<'4' | '2'>('4');
  const [teamResults, setTeamResults] = useState<TeamAnalysisResult | null>(null);
  const [fixtureOutcomes, setFixtureOutcomes] = useState<FixtureOutcome[]>([]);

  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    fetch('/analysis_results.json')
      .then((response) => {
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }
        return response.json();
      })
      .then((data: FetchedAnalysisData) => {
        if (!data.analysis_data || !data.analysis_data.team_analysis) {
          throw new Error("Team analysis data is missing or malformed in the response.");
        }
        setMetadata(data.metadata);
        const teamAnalysis = data.analysis_data.team_analysis;
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
      .catch((fetchError) => {
        console.error("Failed to load analysis results:", fetchError);
        setError(`Failed to load analysis data. (${fetchError.message})`);
      })
      .finally(() => {
        setLoading(false);
      });
  }, [selectedTeamKey]); // Re-fetch or re-process if selectedTeamKey logic changes, though not typical for initial load

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
    return <p role="status" aria-live="polite">Loading detailed analysis...</p>;
  }

  if (error) {
    return <p role="alert" aria-live="assertive" style={{ color: 'red' }}>{error}</p>;
  }

  return (
    <div>
      {metadata && (
        <div className="metadata mb-1">
          <p>Analysis Method: {metadata.method_used}</p>
          <p>Last Updated: {new Date(metadata.timestamp).toLocaleString()}</p>
        </div>
      )}

      <div className="analysis-controls">
        <div className="control-group">
          <label htmlFor="team-select-analysis">Select Team: </label>
          <select id="team-select-analysis" value={selectedTeamKey} onChange={handleTeamChange} aria-controls="team-analysis-results">
            <option value="">--Select a Team--</option>
            {Object.entries(availableTeams).map(([key, name]) => (
              <option key={key} value={key}>{name}</option>
            ))}
          </select>
        </div>

        <fieldset className="control-group">
          <legend>Select Target:</legend>
          <label htmlFor="top4-radio-analysis">
            <input
              type="radio"
              id="top4-radio-analysis"
              name="target-analysis"
              value="4"
              checked={selectedTarget === '4'}
              onChange={handleTargetChange}
              aria-controls="team-analysis-results"
            /> Top 4
          </label>
          <label htmlFor="top2-radio-analysis">
            <input
              type="radio"
              id="top2-radio-analysis"
              name="target-analysis"
              value="2"
              checked={selectedTarget === '2'}
              onChange={handleTargetChange}
              aria-controls="team-analysis-results"
            /> Top 2
          </label>
        </fieldset>
      </div>

      {selectedTeamKey && teamResults && (
        <div id="team-analysis-results" className="analysis-results mt-2">
          <h3>
            {team_full_names[selectedTeamKey] || selectedTeamKey} - Top {selectedTarget} Analysis
          </h3>
          <p>
            <strong>
              Chance to qualify for Top {selectedTarget}: {teamResults.percentage.toFixed(2)}%
            </strong>
          </p>
          <h4>Required / Frequent Outcomes for Qualification:</h4>
          {fixtureOutcomes.length > 0 ? (
            <div className="table-responsive">
              <table>
                <caption>Required or frequent match outcomes for {team_full_names[selectedTeamKey] || selectedTeamKey} to qualify for Top {selectedTarget}.</caption>
                <thead>
                  <tr>
                    <th scope="col">Fixture</th>
                    <th scope="col">Outcome</th>
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
            </div>
          ) : (
            <p>No specific outcomes data available. This often means the chance is 0% or 100%, or the team's qualification does not hinge on specific remaining matches.</p>
          )}
        </div>
      )}
      {!teamResults && selectedTeamKey && !loading && (
         <p className="mt-2">No analysis data available for {team_full_names[selectedTeamKey] || selectedTeamKey} for Top {selectedTarget}. This could be due to the team already being qualified/eliminated or data processing issues.</p>
      )}
      {!selectedTeamKey && !loading && (
        <p className="mt-2">Please select a team to view detailed analysis.</p>
      )}
    </div>
  );
};

export default DetailedTeamAnalysis;
