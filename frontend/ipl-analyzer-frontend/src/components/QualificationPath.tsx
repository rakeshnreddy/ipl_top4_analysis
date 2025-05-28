import React, { useEffect, useState } from 'react';
import { team_full_names, type TeamNames } from '../teamStyles';

interface QualificationPathResult {
  possible: number | null;
  guaranteed: number | null;
  target_matches: number;
}

interface QualificationPathData {
  [target: string]: {
    [teamKey: string]: QualificationPathResult;
  };
}

interface AnalysisMetadata {
  method_used: string;
  timestamp: string;
}

interface FetchedAnalysisData {
  metadata: AnalysisMetadata;
  analysis_data: {
    qualification_path: QualificationPathData;
  };
}

const QualificationPath: React.FC = () => {
  const [pathData, setPathData] = useState<QualificationPathData | null>(null);
  const [metadata, setMetadata] = useState<AnalysisMetadata | null>(null);
  const [availableTeams, setAvailableTeams] = useState<TeamNames>({});
  const [selectedTeamKey, setSelectedTeamKey] = useState<string>('');
  const [selectedTarget, setSelectedTarget] = useState<'4' | '2'>('4');
  const [teamPathResult, setTeamPathResult] = useState<QualificationPathResult | null>(null);

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
        if (!data.analysis_data || !data.analysis_data.qualification_path) {
          // This is a valid scenario if the method isn't exhaustive, so don't throw an error
          // but allow the component to render a message about it.
          setMetadata(data.metadata); // Still set metadata
        } else {
          setMetadata(data.metadata);
          const qualPath = data.analysis_data.qualification_path;
          setPathData(qualPath);

          const teamsInPathAnalysis = qualPath['4'] ? Object.keys(qualPath['4']) : [];
          const validTeams: TeamNames = {};
          teamsInPathAnalysis.forEach(key => {
            if (team_full_names[key]) {
              validTeams[key] = team_full_names[key];
            }
          });
          setAvailableTeams(validTeams);

          if (teamsInPathAnalysis.length > 0 && !selectedTeamKey) {
            setSelectedTeamKey(teamsInPathAnalysis[0]);
          }
        }
        setError(null);
      })
      .catch((fetchError) => {
        console.error("Failed to load analysis results for qualification path:", fetchError);
        setError(`Failed to load analysis data. (${fetchError.message})`);
      })
      .finally(() => {
        setLoading(false);
      });
  }, [selectedTeamKey]);

  useEffect(() => {
    if (pathData && selectedTeamKey && selectedTarget && metadata?.method_used.toLowerCase().includes('exhaustive')) {
      const result = pathData[selectedTarget]?.[selectedTeamKey];
      setTeamPathResult(result || null);
    } else {
      setTeamPathResult(null);
    }
  }, [pathData, selectedTeamKey, selectedTarget, metadata]);

  const handleTeamChange = (event: React.ChangeEvent<HTMLSelectElement>) => {
    setSelectedTeamKey(event.target.value);
  };

  const handleTargetChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setSelectedTarget(event.target.value as '4' | '2');
  };

  if (loading) {
    return <p role="status" aria-live="polite">Loading qualification path analysis...</p>;
  }

  if (error) {
    return <p role="alert" aria-live="assertive" style={{ color: 'red' }}>{error}</p>;
  }

  const isExhaustive = metadata?.method_used.toLowerCase().includes('exhaustive');

  return (
    <div>
      {metadata && (
        <div className="metadata mb-1">
          <p>Analysis Method: {metadata.method_used}</p>
          {!isExhaustive && pathData && ( // Check if pathData is available even if not exhaustive
             <p className="text-warning" role="status">
              Note: Qualification Path analysis is most meaningful and typically only available with the Exhaustive method.
            </p>
          )}
        </div>
      )}

      {!pathData && !loading && !isExhaustive && (
         <p role="status">Qualification Path data is not available for the current analysis method ({metadata?.method_used || 'Unknown'}). This feature requires Exhaustive analysis.</p>
      )}
      
      {isExhaustive && !pathData && !loading && (
         <p role="status">Qualification Path data is available with the Exhaustive method, but it seems to be missing from the results file.</p>
      )}


      {(pathData || isExhaustive) && ( // Show controls if pathData exists OR if method is exhaustive (even if data is missing for some reason)
        <div className="qualification-path-controls">
          <div className="control-group">
            <label htmlFor="team-select-path">Select Team: </label>
            <select id="team-select-path" value={selectedTeamKey} onChange={handleTeamChange} disabled={!isExhaustive || Object.keys(availableTeams).length === 0} aria-controls="qualification-path-results">
              <option value="">--Select a Team--</option>
              {Object.entries(availableTeams).map(([key, name]) => (
                <option key={key} value={key}>{name}</option>
              ))}
            </select>
          </div>

          <fieldset className="control-group">
            <legend>Select Target:</legend>
            <label htmlFor="top4-radio-path">
              <input
                type="radio"
                id="top4-radio-path"
                name="target-path"
                value="4"
                checked={selectedTarget === '4'}
                onChange={handleTargetChange}
                disabled={!isExhaustive}
                aria-controls="qualification-path-results"
              /> Top 4
            </label>
            <label htmlFor="top2-radio-path">
              <input
                type="radio"
                id="top2-radio-path"
                name="target-path"
                value="2"
                checked={selectedTarget === '2'}
                onChange={handleTargetChange}
                disabled={!isExhaustive}
                aria-controls="qualification-path-results"
              /> Top 2
            </label>
          </fieldset>
        </div>
      )}

      {isExhaustive && selectedTeamKey && teamPathResult && (
        <div id="qualification-path-results" className="qualification-path-results mt-2">
          <h3>
            {team_full_names[selectedTeamKey] || selectedTeamKey} - Top {selectedTarget} Path
          </h3>
          <p>
            <strong>Remaining Matches for {team_full_names[selectedTeamKey] || selectedTeamKey}:</strong>{' '}
            {teamPathResult.target_matches}
          </p>
          
          {typeof teamPathResult.possible === 'number' ? (
            <p>
              <strong>Possible Qualification:</strong> Win <strong>{teamPathResult.possible}</strong> match(es) (with favorable results from other matches).
            </p>
          ) : (
            <p><strong>Possible Qualification:</strong> Cannot qualify for Top {selectedTarget} even by winning all remaining matches, or data not applicable.</p>
          )}

          {typeof teamPathResult.guaranteed === 'number' ? (
            <p>
              <strong>Guaranteed Qualification:</strong> Win <strong>{teamPathResult.guaranteed}</strong> match(es) (irrespective of other results).
            </p>
          ) : (
            <p><strong>Guaranteed Qualification:</strong> Cannot guarantee qualification for Top {selectedTarget} based solely on own wins.</p>
          )}
        </div>
      )}
      {isExhaustive && selectedTeamKey && !teamPathResult && !loading && (
         <p className="mt-2">No qualification path data available for {team_full_names[selectedTeamKey] || selectedTeamKey} for Top {selectedTarget}.</p>
      )}
      {isExhaustive && !selectedTeamKey && Object.keys(availableTeams).length > 0 && !loading && (
        <p className="mt-2">Please select a team to view its qualification path.</p>
      )}
    </div>
  );
};

export default QualificationPath;
