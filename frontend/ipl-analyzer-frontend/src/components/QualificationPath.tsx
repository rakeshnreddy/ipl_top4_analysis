import React, { useEffect, useState } from 'react';
import { team_full_names } from '../teamStyles'; import type { TeamNames } from '../teamStyles';

interface QualificationPathResult {
  possible: number | null;
  guaranteed: number | null;
  target_matches: number;
}

interface QualificationPathData {
  [target: string]: { // "2" or "4"
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
    // Other analysis data might also be here
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
    fetch('/analysis_results.json')
      .then((response) => {
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }
        return response.json();
      })
      .then((data: FetchedAnalysisData) => {
        setMetadata(data.metadata);
        if (data.analysis_data && data.analysis_data.qualification_path) {
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

          if (teamsInPathAnalysis.length > 0) {
            setSelectedTeamKey(teamsInPathAnalysis[0]);
          }
        } else {
          setError("Qualification path data is missing in the analysis results.");
        }
        setLoading(false);
      })
      .catch((fetchError) => {
        console.error("Failed to load analysis results for qualification path:", fetchError);
        setError(`Failed to load analysis data. ${fetchError.message}`);
        setLoading(false);
      });
  }, []);

  useEffect(() => {
    if (pathData && selectedTeamKey && selectedTarget && metadata?.method_used.toLowerCase().includes('exhaustive')) {
      const result = pathData[selectedTarget]?.[selectedTeamKey];
      setTeamPathResult(result || null);
    } else {
      setTeamPathResult(null); // Clear if not exhaustive or data missing
    }
  }, [pathData, selectedTeamKey, selectedTarget, metadata]);

  const handleTeamChange = (event: React.ChangeEvent<HTMLSelectElement>) => {
    setSelectedTeamKey(event.target.value);
  };

  const handleTargetChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setSelectedTarget(event.target.value as '4' | '2');
  };

  if (loading) {
    return <p>Loading qualification path analysis...</p>;
  }

  if (error) {
    return <p style={{ color: 'red' }}>{error}</p>;
  }

  const isExhaustive = metadata?.method_used.toLowerCase().includes('exhaustive');

  return (
    <div>
      {metadata && (
        <div style={{ marginBottom: '10px', fontSize: '0.9em', color: '#555' }}>
          <p>Analysis Method: {metadata.method_used}</p>
          {!isExhaustive && (
            <p style={{ color: 'orange' }}>
              Note: Qualification Path analysis is most meaningful with Exhaustive method.
            </p>
          )}
        </div>
      )}

      <div className="qualification-path-controls">
        <div className="control-group">
          <label htmlFor="team-select-path">Select Team: </label>
          <select id="team-select-path" value={selectedTeamKey} onChange={handleTeamChange} disabled={!isExhaustive}>
            {Object.entries(availableTeams).map(([key, name]) => (
              <option key={key} value={key}>{name}</option>
            ))}
          </select>
        </div>

        <div className="control-group">
          <label>Select Target: </label>
          <label htmlFor="top4-radio-path">
            <input
              type="radio"
              id="top4-radio-path"
              name="target-path"
              value="4"
              checked={selectedTarget === '4'}
              onChange={handleTargetChange}
              disabled={!isExhaustive}
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
            /> Top 2
          </label>
        </div>
      </div>

      {!isExhaustive && (
        <p>Qualification Path analysis is only available when Exhaustive method is used.</p>
      )}

      {isExhaustive && selectedTeamKey && teamPathResult && (
        <div className="qualification-path-results">
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
         <p>No qualification path data available for {team_full_names[selectedTeamKey] || selectedTeamKey} for Top {selectedTarget}.</p>
      )}
    </div>
  );
};

export default QualificationPath;
